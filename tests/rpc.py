import unittest
import os

from unittest.mock import patch

import bitcoin_indexer.logger   
import bitcoin_indexer.rpc as rpc


class TestGetBlockClient(unittest.TestCase):
    
    # -----------
    # rpc_url
    # -----------
    @patch.dict(os.environ, {"GETBLOCK_ACCESS_TOKEN": "123456789"}, clear=True)
    def test_rpc_url(self):
        gbc = rpc.GetBlockClient()
        self.assertEqual(gbc.rpc_url, "https://go.getblock.io/123456789")    

    @patch("bitcoin_indexer.rpc.load_dotenv")
    def test_should_fail_rpc_url_without_env_var(self, mock_load_dotenv):
        with patch.dict(os.environ, {}, clear=True):
            try:
                gbc = rpc.GetBlockClient()
                gbc.rpc_url
                assert False
            except RuntimeError:
                assert True

    
if __name__ == "__main__":
    unittest.main()