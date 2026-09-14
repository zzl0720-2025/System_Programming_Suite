open Syntax

let generate program =
  let output=Buffer.create 2048 and labels=ref 0 in
  let emit line = Buffer.add_string output ("  " ^ line ^ "\n") in
  let label name = Buffer.add_string output (name ^ ":\n") in
  let fresh () = incr labels; "branch_" ^ string_of_int !labels in
  let constant register value =
    let n=Int64.of_int32 value in
    if n >= -2048L && n <= 2047L then emit(Printf.sprintf "addi %s, zero, %Ld" register n)
    else (
      let high=Int64.shift_right (Int64.add n 2048L) 12 in
      let low=Int64.sub n (Int64.shift_left high 12) in
      emit(Printf.sprintf "lui %s, %Ld" register (Int64.logand high 0xfffffL));
      emit(Printf.sprintf "addiw %s, %s, %Ld" register register low))
  in
  let push register = emit "addi sp, sp, -16";emit("sd " ^ register ^ ", 0(sp)") in
  let pop register = emit("ld " ^ register ^ ", 0(sp)");emit "addi sp, sp, 16" in
  let rec expression depth env = function
    | Number n -> constant "a0" n
    | Variable name -> emit(Printf.sprintf "ld a0, %d(sp)" ((depth-List.assoc name env)*16))
    | Negate x -> expression depth env x;emit "subw a0, zero, a0"
    | Let(name,value,body) -> expression depth env value;push "a0";expression (depth+1) ((name,depth+1)::env) body;emit "addi sp, sp, 16"
    | If(c,a,b) ->
      let yes=fresh() and no=fresh() and done_=fresh() in
      expression depth env c;emit("bne a0, zero, " ^ yes);emit("jal zero, " ^ no);label yes;
      expression depth env a;emit("jal zero, " ^ done_);label no;expression depth env b;label done_
    | Call(name,args) ->
      List.iteri (fun i arg -> expression (depth+i) env arg;push "a0") args;
      for i=List.length args-1 downto 0 do pop("a" ^ string_of_int i) done;
      emit("jal ra, fn_" ^ name)
    | Binary(op,a,b) ->
      expression depth env a;push "a0";expression (depth+1) env b;pop "t0";
      (match op with
      | "+" -> emit "addw a0, t0, a0" | "-" -> emit "subw a0, t0, a0"
      | "*" -> emit "mulw a0, t0, a0" | "/" -> emit "divw a0, t0, a0" | "%" -> emit "remw a0, t0, a0"
      | "<" -> emit "slt a0, t0, a0" | ">" -> emit "slt a0, a0, t0"
      | "<=" -> emit "slt a0, a0, t0";emit "xori a0, a0, 1"
      | ">=" -> emit "slt a0, t0, a0";emit "xori a0, a0, 1"
      | "==" -> emit "xor a0, t0, a0";emit "sltiu a0, a0, 1"
      | "!=" -> emit "xor a0, t0, a0";emit "sltu a0, zero, a0"
      | _ -> assert false)
  in
  Buffer.add_string output ".text\n.globl _start\n";
  label "_start";
  emit "auipc sp, 4096";
  emit "jal ra, suite_expr";
  constant "t0" 0x10000000l;
  for _=0 to 7 do
    let digit=fresh() and send=fresh() in
    emit "srli t1, a0, 28";emit "andi t1, t1, 15";emit "addi t2, zero, 10";
    emit("blt t1, t2, " ^ digit);emit "addi t1, t1, 87";emit("jal zero, " ^ send);
    label digit;emit "addi t1, t1, 48";label send;emit "sb t1, 0(t0)";emit "slli a0, a0, 4"
  done;
  emit "addi t1, zero, 10";emit "sb t1, 0(t0)";
  constant "t0" 0x100000l;constant "t1" 0x5555l;emit "sw t1, 0(t0)";
  label "halt";emit "jal zero, halt";
  label "suite_expr";push "ra";expression 1 [] program.expression;pop "ra";emit "jalr zero, 0(ra)";
  List.iter (fun f ->
    label("fn_" ^ f.name);push "ra";
    List.iteri (fun i _->push("a" ^ string_of_int i)) f.params;
    let env=List.mapi (fun i name->name,i+2) f.params in
    expression (1+List.length f.params) env f.body;
    if f.params<>[] then emit(Printf.sprintf "addi sp, sp, %d" (16*List.length f.params));
    pop "ra";emit "jalr zero, 0(ra)") program.functions;
  Buffer.contents output
