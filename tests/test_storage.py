from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from frame_app.models import AlbumSnapshot, SourcePhoto
from frame_app.storage import Catalogue


def snapshot(*photos: SourcePhoto) -> AlbumSnapshot:
    return AlbumSnapshot(id="album", title="Test Album", photos=tuple(photos))


class StorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.catalogue = Catalogue(Path(self.temporary.name) / "catalogue.sqlite3")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_newest_unseen_photos_are_selected_first(self) -> None:
        older = SourcePhoto("older", "https://lh3.googleusercontent.com/older", created_at=1)
        newer = SourcePhoto("newer", "https://lh3.googleusercontent.com/newer", created_at=2)
        self.catalogue.sync(snapshot(older, newer), now=100)

        first = self.catalogue.choose_next()
        self.assertIsNotNone(first)
        self.assertEqual(first.id, "newer")
        self.catalogue.mark_shown(first.id, now=101)

        second = self.catalogue.choose_next()
        self.assertIsNotNone(second)
        self.assertEqual(second.id, "older")

    def test_does_not_repeat_current_when_another_photo_exists(self) -> None:
        photos = (
            SourcePhoto("a", "https://lh3.googleusercontent.com/a", created_at=3),
            SourcePhoto("b", "https://lh3.googleusercontent.com/b", created_at=2),
        )
        self.catalogue.sync(snapshot(*photos), now=100)
        self.catalogue.mark_shown("a", now=101)
        self.catalogue.mark_shown("b", now=102)

        selected = self.catalogue.choose_next()
        self.assertIsNotNone(selected)
        self.assertEqual(selected.id, "a")

    def test_removed_album_photo_becomes_inactive(self) -> None:
        a = SourcePhoto("a", "https://lh3.googleusercontent.com/a")
        b = SourcePhoto("b", "https://lh3.googleusercontent.com/b")
        self.catalogue.sync(snapshot(a, b), now=100)
        self.catalogue.sync(snapshot(a), now=200)
        self.assertEqual(self.catalogue.status()["photo_count"], 1)

    def test_random_does_not_repeat_current_photo(self) -> None:
        a = SourcePhoto("a", "https://lh3.googleusercontent.com/a")
        b = SourcePhoto("b", "https://lh3.googleusercontent.com/b")
        self.catalogue.sync(snapshot(a, b), now=100)
        self.catalogue.mark_shown("a", now=101)

        selected = self.catalogue.choose_random()
        self.assertIsNotNone(selected)
        self.assertEqual(selected.id, "b")

    def test_previous_returns_last_other_shown_photo(self) -> None:
        photos = tuple(
            SourcePhoto(name, f"https://lh3.googleusercontent.com/{name}")
            for name in ("a", "b", "c")
        )
        self.catalogue.sync(snapshot(*photos), now=100)
        self.catalogue.mark_shown("a", now=101)
        self.catalogue.mark_shown("b", now=102)
        self.catalogue.mark_shown("c", now=103)

        selected = self.catalogue.choose_previous()
        self.assertIsNotNone(selected)
        self.assertEqual(selected.id, "b")

    def test_focus_point_is_stored_per_photo(self) -> None:
        self.catalogue.set_focus("photo-a", 0.25, 0.75)
        self.assertEqual(self.catalogue.get_focus("photo-a"), (0.25, 0.75))
        self.assertIsNone(self.catalogue.get_focus("photo-b"))
        self.catalogue.clear_focus("photo-a")
        self.assertIsNone(self.catalogue.get_focus("photo-a"))


if __name__ == "__main__":
    unittest.main()
