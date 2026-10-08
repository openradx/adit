import pickle

from adit.core.errors import IncompleteFetchError


def test_incomplete_fetch_error_survives_pickle_round_trip():
    error = IncompleteFetchError("1.2.3", ["1.2.3.1", "1.2.3.2"], 4)

    restored = pickle.loads(pickle.dumps(error))

    assert isinstance(restored, IncompleteFetchError)
    assert restored.study_uid == "1.2.3"
    assert restored.missing_image_uids == ["1.2.3.1", "1.2.3.2"]
    assert restored.image_count == 4
    assert str(restored) == str(error)
