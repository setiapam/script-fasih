import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('tandai_selesai', Path(__file__).with_name('hit_endpoint.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

CODE = '3175040006000100'
PERIOD = 'fd68e454-ba45-4b85-8205-f3bf777ded24'
ITEM = dict(id='assignment-id', surveyPeriodId=PERIOD, smallestRegionFullCode=CODE,
            region={'_id': 'region-id', 'level_1': {'name': 'DKI JAKARTA'}},
            regionId='region-id', regionGroupId='group-id', doneListing=False, doneTarikSample=False)


def response(data, status=200, content_type='application/json'):
    result = Mock(status_code=status, headers={'Content-Type': content_type})
    result.json.return_value = data
    return result


class TestTandaiSelesai(unittest.TestCase):
    def test_parse_user_curl_format(self):
        content = Path(__file__).with_name('curl.example.txt').read_text()
        url, headers, period, payload = module.parse_curl(content)
        self.assertEqual(period, PERIOD)
        self.assertIn('periodeId=', url)
        self.assertIn('SESSION=', headers['Cookie'])
        self.assertEqual(payload['search']['value'], CODE)

    def test_cookie_token_fallback_and_headers(self):
        curl = (f"curl --url '{module.BASE_URL}/datatable?periodeId={PERIOD}' "
                "-H 'content-length: 999' -b 'XSRF-TOKEN=abc%3D; SESSION=s'")
        _, headers, _, _ = module.parse_curl(curl)
        self.assertEqual(headers['X-XSRF-TOKEN'], 'abc=')
        self.assertNotIn('content-length', headers)

    def test_list_validation_and_deduplication(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'list.txt'
            path.write_text(f'# komentar\n\n{CODE}\n{CODE}\n0317504000600010\n')
            self.assertEqual(module.load_targets(path), [CODE, '0317504000600010'])
            path.write_text('123\n')
            with self.assertRaises(ValueError):
                module.load_targets(path)

    def test_payload_matches_browser_and_preserves_region(self):
        original = copy.deepcopy(ITEM)
        payload = module.build_done_payload(ITEM, PERIOD)
        self.assertEqual(payload, original)
        self.assertIsNot(payload['region'], ITEM['region'])
        self.assertFalse(payload['doneListing'])
        with self.assertRaises(ValueError):
            module.build_done_payload(ITEM, 'other-period')
        with self.assertRaises(ValueError):
            module.build_done_payload({'id': 'incomplete'}, PERIOD)

    @patch.object(module.requests, 'post')
    def test_search_requires_exact_match(self, post):
        other = dict(ITEM, id='other', smallestRegionFullCode=CODE + '1')
        post.return_value = response({'data': {'searchData': [other, ITEM]}})
        self.assertEqual(module.search_region('url', {}, {}, CODE), ITEM)
        post.return_value = response({'data': [other]})
        with self.assertRaises(ValueError):
            module.search_region('url', {}, {}, CODE)
        post.return_value = response({'data': [ITEM, dict(ITEM, id='second')]})
        with self.assertRaises(ValueError):
            module.search_region('url', {}, {}, CODE)

    @patch.object(module.requests, 'post')
    def test_pagination(self, post):
        first_page = [dict(ITEM, id=str(n), smallestRegionFullCode='other') for n in range(100)]
        post.side_effect = [response({'data': first_page}), response({'data': [ITEM]})]
        self.assertEqual(module.search_region('url', {}, {}, CODE), ITEM)
        self.assertEqual(post.call_count, 2)

    def test_auth_and_application_failure(self):
        for status in (401, 403):
            with self.assertRaises(module.SessionExpiredException):
                module.read_response(response({}, status))
        with self.assertRaises(module.SessionExpiredException):
            module.read_response(response({}, content_type='text/html'))
        with self.assertRaises(ValueError):
            module.read_response(response({'success': False}))

    def run_main(self, done_result=None, already_done=False):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            folder.joinpath('curl.txt').write_text(Path(__file__).with_name('curl.example.txt').read_text())
            folder.joinpath('list.txt').write_text(CODE + '\n')
            replies = [response({'data': [dict(ITEM, doneListing=already_done)]})]
            if not already_done:
                replies.append(response(done_result))
            with patch.object(module, 'MODULE_DIR', folder), patch('builtins.input', return_value='y'), \
                    patch.object(module.requests, 'post', side_effect=replies) as post, \
                    patch.object(module.time, 'sleep'), patch('builtins.print'):
                module.main()
                log = folder.joinpath('execution.log').read_text()
                workbook = module.load_workbook(folder / module.REPORT_FILE)
                try:
                    row = list(workbook.active.values)[1]
                    self.assertEqual(row[1], CODE)
                    self.assertEqual(workbook.active['B2'].data_type, 's')
                    expected = 'Sudah selesai' if already_done else (
                        'Berhasil' if done_result.get('success') is True else 'Gagal')
                    self.assertEqual(row[2], expected)
                finally:
                    workbook.close()
                return post.call_args_list, log

    def test_report_updates_target_and_preserves_other_periods(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(module, 'MODULE_DIR', Path(temp)):
            def row(period, status):
                return dict(zip(module.REPORT_COLUMNS, (period, CODE, status, 'detail', 'waktu')))
            module.save_report([row(PERIOD, 'Gagal'), row('other-period', 'Berhasil')])
            module.save_report([row(PERIOD, 'Berhasil')])
            workbook = module.load_workbook(Path(temp) / module.REPORT_FILE)
            try:
                rows = list(workbook.active.values)
                self.assertEqual(len(rows), 3)
                self.assertEqual(rows[1][2], 'Berhasil')
                self.assertEqual(rows[2][0], 'other-period')
            finally:
                workbook.close()

    def test_main_posts_current_assignment(self):
        calls, log = self.run_main({'success': True})
        self.assertEqual(calls[1].args[0], module.BASE_URL + '/done')
        self.assertEqual(calls[1].kwargs['json'], ITEM)
        self.assertIn('berhasil=1', log)

    def test_main_skips_completed_server_status(self):
        calls, log = self.run_main(already_done=True)
        self.assertEqual(len(calls), 1)
        self.assertIn('sudah selesai=1', log)

    def test_main_rejects_unconfirmed_success(self):
        _, log = self.run_main({'message': 'unknown'})
        self.assertIn('gagal=1', log)
        self.assertIn('berhasil=0', log)


if __name__ == '__main__':
    unittest.main()
