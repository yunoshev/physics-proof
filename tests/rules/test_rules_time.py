from src.rules import check_t1_time_base, check_t2_fit_frames


def test_rt1_accepts_measured_timestamps():
    assert check_t1_time_base(uses_measured_timestamps=True) is None


def test_rt1_refuses_bare_fps():
    err = check_t1_time_base(uses_measured_timestamps=False, bare_fps=24.0)
    assert err is not None and err[0] == "TIME_BASE_BARE_FPS"


def test_rt2_rejects_dups_and_cuts_without_logged_correction():
    err = check_t2_fit_frames(
        fitted_frames=[10, 11, 12], confirmed_duplicates=[11],
        cuts=[(20, 25)])
    assert err is not None and err[0] == "FIT_INCLUDES_CONTACT_OR_DUP"
    err2 = check_t2_fit_frames(
        fitted_frames=[18, 19, 20, 21], confirmed_duplicates=[],
        cuts=[(20, 25)])
    assert err2 is not None and "cut" in err2[2]


def test_rt2_logged_correction_excuses_listed_frames():
    assert check_t2_fit_frames(
        fitted_frames=[10, 11, 12], confirmed_duplicates=[11],
        cuts=[(20, 25)], corrections={11: "collapsed to one timestamp",
                                      (20, 25): "window excludes cut"}) is None
