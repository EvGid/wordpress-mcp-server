import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os
import json

# Add parent directory to path to import mcp_sse_server
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock environment variables before importing if needed, but the module uses proper defaults/getenv
# However, we rely on the import. 
# Note: if mcp_sse_server executes code at module level (it does: load_dotenv, logging setup), it will run.
# The `if __name__ == "__main__":` block prevents the server from starting.

from mcp_sse_server import WordPressMCP, call_tool

class TestWordPressMCP(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mcp = WordPressMCP("https://example.com", "user", "pass")
        # Mock the httpx client
        self.mcp.client = AsyncMock()

    async def test_create_post_success(self):
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": 123,
            "link": "https://example.com/p/123",
            "title": {"rendered": "Test Title"}
        }
        mock_response.raise_for_status = MagicMock()
        self.mcp.client.post.return_value = mock_response

        # Execute
        result = await self.mcp.create_post("Test Title", "<p>Content</p>")

        # Verify
        self.assertTrue(result["success"])
        self.assertEqual(result["post_id"], 123)
        self.assertIn("created successfully", result["message"])
        
        # Verify call arguments
        args, kwargs = self.mcp.client.post.call_args
        self.assertEqual(kwargs["json"]["title"], "Test Title")
        self.assertEqual(kwargs["json"]["status"], "publish")

    async def test_create_post_failure(self):
        # Mock exception
        import httpx
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        error = httpx.HTTPStatusError("Error", request=MagicMock(), response=mock_response)
        
        # We need to simulate the post raising the error when raise_for_status is called
        # OR just simulationg post raising it if the implementation does that.
        # The implementation calls response.raise_for_status().
        
        mock_response.raise_for_status.side_effect = error
        self.mcp.client.post.return_value = mock_response

        # Execute
        result = await self.mcp.create_post("Title", "Content")

        # Verify
        self.assertFalse(result["success"])
        self.assertIn("HTTP error: 500", result["message"])

    async def test_update_post_success(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": 123,
            "link": "https://example.com/p/123"
        }
        mock_response.raise_for_status = MagicMock()
        self.mcp.client.post.return_value = mock_response

        result = await self.mcp.update_post(123, title="New Title")

        self.assertTrue(result["success"])
        self.assertEqual(result["post_id"], 123)

    async def test_update_post_no_fields(self):
        result = await self.mcp.update_post(123)
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "No fields to update")
        self.mcp.client.post.assert_not_called()

    async def test_get_posts_success(self):
        mock_response = MagicMock()
        mock_response.headers = {"X-WP-Total": "50"}
        mock_response.json.return_value = [
            {
                "id": 1,
                "title": {"rendered": "Post 1"},
                "excerpt": {"rendered": "Excerpt 1"},
                "status": "publish",
                "link": "http://example.com/1",
                "date": "2023-01-01"
            },
            {
                "id": 2,
                "title": {"rendered": "Post 2"},
                "excerpt": {"rendered": "Excerpt 2"},
                "status": "draft",
                "link": "http://example.com/2",
                "date": "2023-01-02"
            }
        ]
        mock_response.raise_for_status = MagicMock()
        self.mcp.client.get.return_value = mock_response

        result = await self.mcp.get_posts(page=1, per_page=5)

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["total"], 50)
        self.assertEqual(result["posts"][0]["title"], "Post 1")

    async def test_delete_post_success(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        self.mcp.client.delete.return_value = mock_response

        result = await self.mcp.delete_post(123)

        self.assertTrue(result["success"])
        self.assertEqual(result["post_id"], 123)
        
        # Verify force=True was used
        args, kwargs = self.mcp.client.delete.call_args
        self.assertEqual(kwargs["params"]["force"], True)

class TestToolCalls(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # We need to patch the global wordpress_mcp variable in mcp_sse_server
        self.patcher = patch('mcp_sse_server.wordpress_mcp', new_callable=AsyncMock)
        self.mock_wp_mcp = self.patcher.start()
        
        # Configure mock methods to return dummy values matching expected return types
        self.mock_wp_mcp.create_post.return_value = {"success": True, "post_id": 1, "message": "Created"}
        self.mock_wp_mcp.update_post.return_value = {"success": True, "post_id": 1, "message": "Updated"}
        self.mock_wp_mcp.get_posts.return_value = {"success": True, "posts": [], "count": 0}
        self.mock_wp_mcp.delete_post.return_value = {"success": True, "post_id": 1, "message": "Deleted"}

    async def asyncTearDown(self):
        self.patcher.stop()

    async def test_call_tool_create_post(self):
        args = {"title": "Test", "content": "Content"}
        result_list = await call_tool("create_post", args)
        
        # Result is a list of TextContent
        result_json = json.loads(result_list[0].text)
        self.assertTrue(result_json["success"])
        self.mock_wp_mcp.create_post.assert_called_with(
            title="Test", content="Content", excerpt="", status="publish"
        )

    async def test_call_tool_unknown(self):
        result_list = await call_tool("unknown_tool", {})
        result_json = json.loads(result_list[0].text)
        self.assertFalse(result_json["success"])
        self.assertIn("Unknown tool", result_json["message"])

    async def test_call_tool_missing_arg(self):
        # call_tool expects arguments to match. 
        # But wait, call_tool implementation in mcp_sse_server accesses arguments["title"] directly
        # so it will raise KeyError if missing.
        # The create_post tool function in mcp_sse_server.py:
        # result = await wordpress_mcp.create_post(title=arguments["title"], ...)
        # It catches KeyError and returns error message.
        
        args = {"content": "Content"} # Missing title
        result_list = await call_tool("create_post", args)
        result_json = json.loads(result_list[0].text)
        
        self.assertFalse(result_json["success"])
        self.assertIn("Missing required argument", result_json["message"])

if __name__ == "__main__":
    unittest.main()
