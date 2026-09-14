import json
from pathlib import Path
import shutil
import struct
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import compiler_driver
import engine


def compile_source(source,verify=False):
    return engine.run({'schema_version':1,'module':'compiler','source':source,'verify':verify})


PROGRAMS = [
    ('2 + 3 * 4',14), ('(2 + 3) * 4',20),
    ('let x = 9 in let x = x + 1 in x * x',100),
    ('if -1 then 17 else 23',17),
    ('fn loop(x) = loop(x); if 0 then loop(1) else 7',7),
    ('fn factorial(n) = if n <= 1 then 1 else n * factorial(n - 1); factorial(6)',720),
    ('fn even(n) = if n == 0 then 1 else odd(n-1); fn odd(n) = if n == 0 then 0 else even(n-1); even(10)',1),
    ('fn mix(a,b,c,d) = a * 1000 + b * 100 + c * 10 + d; fn twice(x) = x * 2; let x = 1 in mix(x,twice(x),twice(x)+1,twice(twice(x)))',1234),
    ('fn sub(a,b) = a-b; sub(sub(10,3),sub(8,6))',5),
    ('fn answer() = 42; answer()',42),
    ('2147483647 + 1',-2147483648), ('-2147483648 - 1',2147483647),
    ('-2147483648 / -1',-2147483648), ('-2147483648 % -1',0),
    ('9 / 0',-1), ('-9 % 0',-9), ('-9 / 2',-4), ('-9 % 2',-1),
    ('(3 > 2) + (2 < 3) + (2 <= 2) + (3 >= 3) + (2 != 3) + (4 == 4)',6),
    ('(-2147483648 < 1) + (2147483647 > -1)',2),
    ('let x = 4095 in x + 4096 + 2048 - 2049',8190),
]


class CompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler_driver.build()

    def test_reference_golden_programs(self):
        for source,expected in PROGRAMS:
            with self.subTest(source=source):
                result=compile_source(source)
                self.assertEqual(result['reference_result'],expected)
                self.assertEqual(result['verification']['status'],'not-requested')
                self.assertEqual([e['stage'] for e in result['events']],['lex','parse','check','interpret','emit','execute'])

    @unittest.skipUnless(shutil.which('qemu-system-riscv64'),'QEMU is not installed')
    def test_riscv_execution_matches_golden_results(self):
        for source,expected in PROGRAMS:
            with self.subTest(source=source):
                result=compile_source(source,True)
                self.assertEqual(result['verification']['status'],'passed',result['verification'])
                self.assertEqual(result['verification']['result'],expected)
                self.assertTrue(result['summary']['verified'])

    def test_diagnostics_by_stage(self):
        cases=[('2 @ 3','lex'), ('let x = in 3','parse'), ('missing + 1','semantic'),
               ('fn f(x) = x; f(1,2)','semantic'), ('fn f(x,x) = x; f(1,2)','semantic'),
               ('fn f() = 1; fn f() = 2; f()','semantic'),
               ('fn f(x) = f(x); f(1)','reference'), ('2147483648','parse')]
        for source,stage in cases:
            with self.subTest(source=source):
                with self.assertRaisesRegex(ValueError,stage):compile_source(source)

    def test_tokens_keep_source_positions(self):
        result=compile_source('# start\n2 +\n 3')
        self.assertEqual(result['tokens'],[{'text':'2','line':2,'column':1},{'text':'+','line':2,'column':3},{'text':'3','line':3,'column':2}])

    def test_missing_qemu_is_reported_without_claiming_verification(self):
        with patch('compiler_driver.shutil.which',return_value=None):
            result=compile_source('1 + 2',True)
        self.assertEqual(result['verification']['status'],'unavailable')
        self.assertFalse(result['summary']['verified'])
        self.assertIsNone(result['verification']['result'])

    def test_elf_header_and_known_instruction_encoding(self):
        elf=compiler_driver.assemble('.text\n_start:\n  addi a0, zero, 42\n  addw a0, a0, a1\n  jal zero, _start\n')
        self.assertEqual(elf[:7],b'\x7fELF\x02\x01\x01')
        self.assertEqual(struct.unpack_from('<H',elf,18)[0],243)
        self.assertEqual(struct.unpack_from('<Q',elf,24)[0],0x80000000)
        self.assertEqual(struct.unpack_from('<III',elf,4096),(0x02a00513,0x00b5053b,0xff9ff06f))
        with self.assertRaisesRegex(ValueError,'does not fit'):
            compiler_driver.assemble('_start:\n  addi a0, zero, 5000\n')


if __name__=='__main__':unittest.main()
