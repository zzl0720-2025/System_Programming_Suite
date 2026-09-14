import contextlib
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import engine
import module_api
from suite import Handler, EXAMPLES


class QuietHandler(Handler):
    def log_message(self,*args):
        pass


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        engine.build();module_api.build_native()
        try:
            cls.server=ThreadingHTTPServer(('127.0.0.1',0),QuietHandler)
        except PermissionError:
            raise unittest.SkipTest('Local socket binding is unavailable in this environment')
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'
        cls.worker=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.worker.join()

    def fetch(self,path,config=None):
        request=Request(self.base+path,data=json.dumps(config).encode() if config is not None else None,
                        headers={'Content-Type':'application/json'})
        with urlopen(request,timeout=20) as response:
            return json.load(response)

    def test_catalog_and_all_module_runs(self):
        health=self.fetch('/api/health');catalog=self.fetch('/api/examples')
        self.assertEqual(set(health['modules']),set(EXAMPLES))
        self.assertEqual(set(catalog),set(EXAMPLES))
        for module,config in catalog.items():
            if module=='compiler':config['verify']=False
            with self.subTest(module=module):
                self.assertEqual(self.fetch('/api/run',config),engine.run(config))

    def test_comparison_endpoint(self):
        config=self.fetch('/api/examples')['disk']
        self.assertEqual(self.fetch('/api/compare',config),engine.compare(config))

    def test_invalid_input_returns_json_and_server_recovers(self):
        for config in ({'module':[]}, {'schema_version':1,'module':'cpu','processes':[]}, []):
            with self.assertRaises(HTTPError) as caught:self.fetch('/api/run',config)
            self.assertEqual(caught.exception.code,400)
            self.assertIn('error',json.load(caught.exception))
        self.assertEqual(self.fetch('/api/health')['status'],'ready')

    def test_generated_artifact_download(self):
        result=self.fetch('/api/run',{'schema_version':1,'module':'compiler','source':'42','verify':False})
        for suffix in ('s','elf'):
            with urlopen(self.base+f"/api/artifacts/{result['artifact_id']}/program.{suffix}") as response:
                data=response.read()
                self.assertIn('attachment',response.headers['Content-Disposition'])
                self.assertEqual(data,(engine.ROOT/'build'/'artifacts'/result['artifact_id']/f'program.{suffix}').read_bytes())
        with self.assertRaises(HTTPError) as caught:
            self.fetch('/api/artifacts/'+'0'*24+'/program.elf')
        self.assertEqual(caught.exception.code,404)


if __name__=='__main__':unittest.main()
