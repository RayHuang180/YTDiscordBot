"""Compatibility fallback for pages missing __INITIAL_STATE__.

Uses the video detail API, as proposed in yt-dlp/yt-dlp#17898.
Keep the installed extractor's format selection and multipart handling.
"""

import json

from yt_dlp.extractor.bilibili import BiliBiliIE as OriginalBiliBiliIE


class BiliBiliIE(OriginalBiliBiliIE):
    _VALID_URL = OriginalBiliBiliIE._VALID_URL.replace(
        "bilibili\\.com/", "bilibili\\.com/(?:[a-z]{2}(?:-Hans)?/)?", 1
    )

    def _download_webpage_handle(self, url, video_id, *args, **kwargs):
        webpage, handle = super()._download_webpage_handle(url, video_id, *args, **kwargs)
        if not webpage or not self.suitable(url) or not self.suitable(handle.url):
            return webpage, handle
        state = self._search_json(
            r'window\.__INITIAL_STATE__\s*=', webpage, 'initial state', video_id, default=None
        )
        risk = self._search_json(
            r'\bwindow\._riskdata_\s*=', webpage, 'risk', video_id, default={}
        )
        if state or risk.get('v_voucher'):
            return webpage, handle

        match = self._match_valid_url(url)
        prefix, identifier = match.group('prefix', 'id')
        query = {'platform': 'web'}
        query['bvid' if prefix.upper() == 'BV' else 'aid'] = (
            'BV' + identifier if prefix.upper() == 'BV' else identifier
        )
        headers = dict(kwargs.get('headers') or {})
        headers.update(Referer='https://www.bilibili.com/', Origin='https://www.bilibili.com')
        detail = self._download_json(
            'https://api.bilibili.com/x/web-interface/wbi/view/detail', video_id,
            query=self._sign_wbi(query, video_id), headers=headers,
            note='Downloading video details (page compatibility fallback)', fatal=False,
        )
        data = (detail or {}).get('data') or {}
        video = data.get('View') or {}
        # Leave redirects and API failures to the original extractor.
        if not video.get('bvid') or video.get('redirect_url'):
            return webpage, handle
        state = {
            'videoData': video,
            'upData': video.get('owner') or {},
            'tags': data.get('Tags') or [],
        }
        webpage += '\n<script>window.__INITIAL_STATE__=' + json.dumps(state) + ';</script>'
        return webpage, handle
