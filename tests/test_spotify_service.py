import unittest
from unittest.mock import patch

import spotify_service


EMBED_HTML = """
<html><head><meta property="og:title" content="Pilihan Pagi on Spotify"></head>
<body><script id="__NEXT_DATA__" type="application/json">
{"props":{"pageProps":{"playlist":{"items":[
  {"track":{"uri":"spotify:track:first","name":"Lagu Pertama","artists":[{"name":"Artis A"}]}},
  {"track":{"uri":"spotify:track:second","name":"Lagu Kedua","artists":[{"name":"Artis B"}]}},
  {"track":{"uri":"spotify:track:first","name":"Lagu Pertama","artists":[{"name":"Artis A"}]}}
]}}}}
</script></body></html>
"""


class SpotifyEmbedImportTests(unittest.TestCase):
    def test_get_playlist_id_accepts_url_and_uri(self):
        self.assertEqual(
            spotify_service.get_playlist_id("https://open.spotify.com/playlist/abc123?si=x"),
            "abc123",
        )
        self.assertEqual(spotify_service.get_playlist_id("spotify:playlist:xyz987"), "xyz987")

    def test_scrape_embed_uses_html_title_as_playlist_name_fallback(self):
        parser = spotify_service._SpotifyEmbedParser()
        parser.feed("<title>Playlist Sore on Spotify</title>")
        parser.close()

        self.assertEqual(
            spotify_service._clean_playlist_name(parser.playlist_name, "Playlist Spotify"),
            "Playlist Sore",
        )

    def test_extract_playlist_name_from_hydration_payload(self):
        payload = {"uri": "spotify:playlist:abc123", "name": "Pilihan Malam"}

        self.assertEqual(spotify_service._extract_playlist_name([payload]), "Pilihan Malam")

    @patch("spotify_service.requests.get")
    def test_scrape_embed_extracts_metadata_and_unique_tracks(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = EMBED_HTML
        mock_get.return_value.raise_for_status.return_value = None

        name, tracks = spotify_service.scrape_spotify_embed("abc123")

        self.assertEqual(name, "Pilihan Pagi")
        self.assertEqual(tracks, [("Lagu Pertama", "Artis A"), ("Lagu Kedua", "Artis B")])
        mock_get.assert_called_once_with(
            "https://open.spotify.com/embed/playlist/abc123",
            headers=spotify_service.SPOTIFY_EMBED_HEADERS,
            timeout=20,
        )


if __name__ == "__main__":
    unittest.main()
