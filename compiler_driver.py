"""OCaml front end, RV64 instruction encoding, and QEMU execution."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
BINARY = ROOT / "build" / "suite-compiler"
BASE = 0x80000000


def build():
    sources = [ROOT / "compiler" / name for name in ("syntax.ml", "eval.ml", "codegen.ml", "main.ml")]
    if BINARY.exists() and BINARY.stat().st_mtime >= max(p.stat().st_mtime for p in sources):
        return
    compiler = shutil.which("ocamlc")
    if not compiler:
        raise ValueError("The compilation module requires ocamlc. Install OCaml and put ocamlc on PATH.")
    BINARY.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ocaml-", dir=BINARY.parent) as directory:
        for source in sources:
            shutil.copyfile(source, Path(directory) / source.name)
        process = subprocess.run([compiler, "-o", "suite-compiler", *[p.name for p in sources]],
                                 cwd=directory, capture_output=True, text=True)
        if process.returncode:
            raise ValueError("OCaml build failed:\n" + process.stderr)
        os.replace(Path(directory) / "suite-compiler", BINARY)


REGISTERS = {"zero": 0, "ra": 1, "sp": 2, "t0": 5, "t1": 6, "t2": 7,
             "a0": 10, "a1": 11, "a2": 12, "a3": 13}


def assemble(assembly):
    labels, instructions = {}, []
    for raw in assembly.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("."):
            continue
        if line.endswith(":"):
            name = line[:-1]
            if name in labels:
                raise ValueError(f"Duplicate assembly label: {name}")
            labels[name] = len(instructions) * 4
        else:
            instructions.append(re.split(r"[\s,()]+", line.rstrip(")")))
    if labels.get("_start") != 0:
        raise ValueError("The RISC-V image must begin at _start.")

    def reg(value):
        if value not in REGISTERS:
            raise ValueError(f"Unsupported register: {value}")
        return REGISTERS[value]

    def immediate(value, bits):
        number = int(value, 0)
        if not -(1 << (bits-1)) <= number < (1 << (bits-1)):
            raise ValueError(f"Immediate {number} does not fit {bits} signed bits.")
        return number & ((1 << bits)-1)

    output = bytearray()
    r_ops = {"addw": (0x3b,0,0), "subw": (0x3b,0,32), "mulw": (0x3b,0,1),
             "divw": (0x3b,4,1), "remw": (0x3b,6,1), "slt": (0x33,2,0),
             "sltu": (0x33,3,0), "xor": (0x33,4,0)}
    i_ops = {"addi": (0x13,0), "addiw": (0x1b,0), "andi": (0x13,7),
             "xori": (0x13,4), "sltiu": (0x13,3), "slli": (0x13,1), "srli": (0x13,5)}
    for index, parts in enumerate(instructions):
        op, *args = parts
        if op in r_ops:
            rd,rs1,rs2=map(reg,args);opcode,f3,f7=r_ops[op]
            word=f7<<25 | rs2<<20 | rs1<<15 | f3<<12 | rd<<7 | opcode
        elif op in i_ops:
            rd,rs1=map(reg,args[:2]);imm=immediate(args[2],12);opcode,f3=i_ops[op]
            if op in ("slli","srli") and not 0 <= int(args[2]) < 64:
                raise ValueError("Shift amount must be 0 to 63.")
            word=imm<<20 | rs1<<15 | f3<<12 | rd<<7 | opcode
        elif op in ("lui","auipc"):
            rd=reg(args[0]);imm=int(args[1],0)
            if not 0 <= imm < 1<<20:
                raise ValueError("Upper immediate is out of range.")
            word=imm<<12 | rd<<7 | (0x37 if op=="lui" else 0x17)
        elif op in ("ld","jalr"):
            rd=reg(args[0]);imm=immediate(args[1],12);rs1=reg(args[2])
            word=imm<<20 | rs1<<15 | (3 if op=="ld" else 0)<<12 | rd<<7 | (0x03 if op=="ld" else 0x67)
        elif op in ("sd","sw","sb"):
            rs2=reg(args[0]);imm=immediate(args[1],12);rs1=reg(args[2]);f3={"sd":3,"sw":2,"sb":0}[op]
            word=(imm>>5)<<25 | rs2<<20 | rs1<<15 | f3<<12 | (imm&31)<<7 | 0x23
        elif op in ("beq","bne","blt"):
            rs1,rs2=map(reg,args[:2]);delta=labels[args[2]]-4*index;imm=immediate(str(delta),13)
            if delta%2:
                raise ValueError("Unaligned branch target.")
            word=((imm>>12)&1)<<31 | ((imm>>5)&63)<<25 | rs2<<20 | rs1<<15 | {"beq":0,"bne":1,"blt":4}[op]<<12 | ((imm>>1)&15)<<8 | ((imm>>11)&1)<<7 | 0x63
        elif op=="jal":
            rd=reg(args[0]);delta=labels[args[1]]-4*index;imm=immediate(str(delta),21)
            if delta%2:
                raise ValueError("Unaligned jump target.")
            word=((imm>>20)&1)<<31 | ((imm>>1)&1023)<<21 | ((imm>>11)&1)<<20 | ((imm>>12)&255)<<12 | rd<<7 | 0x6f
        else:
            raise ValueError(f"Unsupported generated instruction: {op}")
        output.extend(struct.pack("<I",word))
    ident=b"\x7fELF\x02\x01\x01"+b"\0"*9
    header=struct.pack("<16sHHIQQQIHHHHHH",ident,2,243,1,BASE,64,0,0,64,56,1,0,0,0)
    segment=struct.pack("<IIQQQQQQ",1,5,4096,BASE,BASE,len(output),len(output),4096)
    return header+segment+b"\0"*(4096-len(header)-len(segment))+output


def run(config):
    build()
    process = subprocess.run([str(BINARY)], input=config["source"], capture_output=True, text=True, timeout=10)
    try:
        compiled = json.loads(process.stdout)
    except json.JSONDecodeError:
        raise ValueError("The compiler did not return a valid result: " + process.stderr)
    if process.returncode:
        error=compiled.get("error",{})
        location = f" at {error['line']}:{error['column']}" if error.get("line", 0) > 0 else ""
        raise ValueError(f"{error.get('stage','compiler')}{location}: {error.get('message','Compilation failed')}")
    elf=assemble(compiled["assembly"])
    key=hashlib.sha256(compiled["assembly"].encode()).hexdigest()[:24]
    artifact_dir=ROOT/"build"/"artifacts"/key
    artifact_dir.mkdir(parents=True,exist_ok=True)
    # A temporary sibling keeps downloads complete during concurrent requests.
    for name,data in (("program.s",compiled["assembly"].encode()),("program.elf",elf)):
        fd,path=tempfile.mkstemp(dir=artifact_dir)
        with os.fdopen(fd,"wb") as stream:
            stream.write(data)
        os.replace(path,artifact_dir/name)
    verification={"status":"not-requested","result":None}
    qemu=shutil.which("qemu-system-riscv64")
    if config.get("verify",True):
        if not qemu:
            verification={"status":"unavailable","result":None,"message":"Install qemu-system-riscv64 to execute the generated ELF."}
        else:
            try:
                execution=subprocess.run([qemu,"-machine","virt","-accel","tcg","-cpu","rv64","-m","128M",
                    "-bios","none","-kernel",str(artifact_dir/"program.elf"),"-display","none","-monitor","none","-serial","stdio"],capture_output=True,timeout=10)
                match=re.search(rb"(?m)^([0-9a-f]{8})\r?$",execution.stdout)
                result=int(match[1],16) if match else None
                if result is not None and result>=2**31: result-=2**32
                passed=execution.returncode==0 and result==compiled["reference_result"]
                verification={"status":"passed" if passed else "failed","result":result,
                              "returncode":execution.returncode,"stderr":execution.stderr.decode(errors="replace")[:2000]}
            except subprocess.TimeoutExpired:
                verification={"status":"timeout","result":None,"message":"QEMU did not finish within 10 seconds."}
    events=[
        {"stage":"lex","outcome":"tokens","description":"Split source into tokens with line and column positions.","tokens":compiled["tokens"]},
        {"stage":"parse","outcome":"syntax-tree","description":"Build a tree using precedence and lexical binding.","ast":compiled["ast"]},
        {"stage":"check","outcome":"semantic-checks","description":"Check variable scope, function names, and argument counts."},
        {"stage":"interpret","outcome":"reference","description":"Evaluate the tree with signed 32-bit arithmetic.","result":compiled["reference_result"]},
        {"stage":"emit","outcome":"assembly","description":"Generate RV64IM instructions with 16-byte aligned stack slots.","assembly":compiled["assembly"]},
        {"stage":"execute","outcome":verification["status"],"description":"Assemble an ELF image and compare QEMU execution with the reference interpreter.","verification":verification},
    ]
    for index,event in enumerate(events): event["index"]=index
    return {"module":"compiler",**compiled,"verification":verification,"events":events,"artifact_id":key,
            "summary":{"tokens":len(compiled["tokens"]),"functions":len(compiled["ast"]["functions"]),
                       "reference_result":compiled["reference_result"],"qemu_result":verification["result"],
                       "verified":verification["status"]=="passed","elf_bytes":len(elf)}}
