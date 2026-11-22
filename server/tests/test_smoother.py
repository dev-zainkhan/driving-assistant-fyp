import pytest

from app.core.smoother import Smoother


def test_first_update_predicts_same_box():
    s = Smoother()
    s.update(1, (0.1, 0.1, 0.2, 0.2), 0.0)
    assert s.predict(1, 0.1) == (0.1, 0.1, 0.2, 0.2)


def test_linear_motion_is_predicted():
    s = Smoother(alpha=1.0)  # no averaging: velocity = last instant velocity
    s.update(1, (0.10, 0.1, 0.20, 0.2), 0.0)
    s.update(1, (0.20, 0.1, 0.30, 0.2), 1.0)  # moving +0.1 per second in x
    p = s.predict(1, 1.2)
    assert p[0] == pytest.approx(0.22) and p[2] == pytest.approx(0.32)


def test_prediction_is_capped():
    s = Smoother(alpha=1.0, max_predict_s=0.3)
    s.update(1, (0.1, 0.1, 0.2, 0.2), 0.0)
    s.update(1, (0.2, 0.1, 0.3, 0.2), 1.0)
    assert s.predict(1, 5.0)[0] == pytest.approx(0.23)  # only 0.3 s of extrapolation


def test_prediction_clamped_to_frame():
    s = Smoother(alpha=1.0, max_predict_s=10)
    s.update(1, (0.8, 0.1, 0.9, 0.2), 0.0)
    s.update(1, (0.9, 0.1, 1.0, 0.2), 0.1)
    assert max(s.predict(1, 5.0)) <= 1.0


def test_track_removed_after_drop_time():
    s = Smoother(drop_s=0.7)
    s.update(1, (0.1, 0.1, 0.2, 0.2), 0.0)
    s.update(2, (0.5, 0.5, 0.6, 0.6), 0.5)
    assert s.prune(0.71) == [1]
    assert s.predict(1, 0.8) is None and s.predict(2, 0.8) is not None
