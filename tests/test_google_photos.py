import json
import unittest

from frame_app.sources.google_photos import (
    GooglePhotosError,
    GooglePhotosPublicAlbum,
)


class GooglePhotosTests(unittest.TestCase):
    def test_extracts_canonical_identity(self) -> None:
        page = (
            '<html><head><link href="https://photos.google.com/share/album123?key=key456" '
            'rel="canonical"></head></html>'
        )
        canonical = GooglePhotosPublicAlbum._canonical_from_html(page)
        self.assertEqual(
            GooglePhotosPublicAlbum._album_identity(canonical, canonical),
            ("album123", "key456"),
        )

    def test_rejects_non_google_link(self) -> None:
        with self.assertRaises(GooglePhotosError):
            GooglePhotosPublicAlbum("https://example.com/photos")

    def test_decodes_album_rpc_and_photo_fields(self) -> None:
        payload = [
            None,
            [
                [
                    "photo-a",
                    ["https://lh3.googleusercontent.com/example", 2000, 1500],
                    1_700_000_000_000,
                ]
            ],
            None,
            ["album-a", "Holiday"],
        ]
        envelope = [["wrb.fr", "snAcKc", json.dumps(payload)]]
        decoded = GooglePhotosPublicAlbum._decode_rpc(
            ")]}'\n" + json.dumps(envelope), "snAcKc"
        )
        photos = GooglePhotosPublicAlbum._photos_from_payload(decoded)
        self.assertEqual(len(photos), 1)
        self.assertEqual(photos[0].id, "photo-a")
        self.assertEqual(photos[0].width, 2000)
        self.assertEqual(photos[0].height, 1500)
        self.assertEqual(photos[0].created_at, 1_700_000_000_000)

    def test_ignores_untrusted_image_host(self) -> None:
        payload = [None, [["photo-a", ["https://example.com/image.jpg", 10, 10], 1]]]
        self.assertEqual(GooglePhotosPublicAlbum._photos_from_payload(payload), [])


if __name__ == "__main__":
    unittest.main()
