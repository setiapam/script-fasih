import unittest
import unittest.mock
import os
import tempfile
import re

# Import the parse_curl function
from hit_endpoint import parse_curl

class TestHitEndpoint(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory and file
        self.test_dir = tempfile.TemporaryDirectory()
        
    def tearDown(self):
        # Cleanup directory
        self.test_dir.cleanup()

    def create_temp_curl_file(self, content):
        temp_file_path = os.path.join(self.test_dir.name, "temp_curl.txt")
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return temp_file_path

    def test_parse_curl_case_sensitive(self):
        content = """curl 'https://example.com/api/test' \\
  -H 'Cookie: foo=bar; XSRF-TOKEN=secret_token' \\
  -H 'X-XSRF-TOKEN: secret_token'"""
        filepath = self.create_temp_curl_file(content)
        url, cookie, xsrf = parse_curl(filepath)
        self.assertEqual(url, "https://example.com/api/test")
        self.assertEqual(cookie, "foo=bar; XSRF-TOKEN=secret_token")
        self.assertEqual(xsrf, "secret_token")

    def test_parse_curl_case_insensitive(self):
        content = """curl 'https://example.com/api/test' \\
  -H 'cookie: foo=bar; XSRF-TOKEN=secret_token' \\
  -H 'x-xsrf-token: secret_token'"""
        filepath = self.create_temp_curl_file(content)
        url, cookie, xsrf = parse_curl(filepath)
        self.assertEqual(url, "https://example.com/api/test")
        self.assertEqual(cookie, "foo=bar; XSRF-TOKEN=secret_token")
        self.assertEqual(xsrf, "secret_token")

    @unittest.mock.patch('requests.get')
    def test_fetch_all_users_success(self, mock_get):
        from hit_endpoint import fetch_all_users
        
        # Mock API response
        mock_response = unittest.mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": "Allocations by user retrieved successfully.",
            "data": {
                "content": [
                    {
                        "userId": "user-123",
                        "email": "test@gmail.com",
                        "regions": [
                            {"allocationId": "alloc-456"}
                        ]
                    }
                ]
            }
        }
        mock_get.return_value = mock_response
        
        url = "https://example.com/api/allocations-view/by-user?surveyRoleId=1&surveyPeriodId=2"
        headers = {}
        users = fetch_all_users(url, headers, "Pencacah")
        
        self.assertEqual(users, {"test@gmail.com": "alloc-456"})
        mock_get.assert_called_once()

    def test_normalize_email(self):
        from hit_endpoint import normalize_email
        self.assertEqual(normalize_email("bagas.kurniawan@bps.goid"), "bagas.kurniawan@bps.go.id")
        self.assertEqual(normalize_email("test@bps.go"), "test@bps.go.id")
        self.assertEqual(normalize_email("user@bps.goid.id"), "user@bps.go.id")
        self.assertEqual(normalize_email("normal@gmail.com"), "normal@gmail.com")

    def test_extract_survey_period_id(self):
        from hit_endpoint import extract_survey_period_id_from_file
        content = """curl 'https://fasih-sm.bps.go.id/app/api/assignment-general/api/assign-by-selection-allocation/074028fe-24ed-4ccd-afe5-6b6aec27e13e' \\
  -H 'Cookie: foo=bar'"""
        filepath = self.create_temp_curl_file(content)
        survey_period_id = extract_survey_period_id_from_file(filepath)
        self.assertEqual(survey_period_id, "074028fe-24ed-4ccd-afe5-6b6aec27e13e")

    def test_extract_survey_period_id_from_datatable(self):
        from hit_endpoint import extract_survey_period_id_from_file
        content = """curl 'https://fasih-sm.bps.go.id/app/api/analytic/api/v2/assignment/datatable-all-user-survey-periode' \\
  -H 'Cookie: foo=bar' \\
  --data-raw '{"assignmentExtraParam":{"surveyPeriodId":"074028fe-24ed-4ccd-afe5-6b6aec27e13e"}}'"""
        filepath = self.create_temp_curl_file(content)
        survey_period_id = extract_survey_period_id_from_file(filepath)
        self.assertEqual(survey_period_id, "074028fe-24ed-4ccd-afe5-6b6aec27e13e")

if __name__ == '__main__':
    import unittest.mock
    unittest.main()
