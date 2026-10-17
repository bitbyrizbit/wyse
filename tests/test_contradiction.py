from wyse.belief.contradiction import resolve


def test_higher_trust_wins_and_loser_is_contested():
    rank = {"web": (1, 1), "sys": (5, 1)}
    assert resolve({"web", "sys"}, [("sys", "web")], rank) == {"web"}


def test_equal_standing_contests_both_sides():
    rank = {"a": (3, 1), "b": (3, 1)}
    assert resolve({"a", "b"}, [("a", "b")], rank) == {"a", "b"}


def test_more_independent_sources_break_a_tie():
    rank = {"a": (3, 2), "b": (3, 1)}
    assert resolve({"a", "b"}, [("a", "b")], rank) == {"b"}


def test_unsupported_partner_causes_no_contest():
    assert resolve({"a"}, [("a", "b")], {"a": (3, 1)}) == set()


def test_unrelated_claims_are_left_alone():
    rank = {"a": (1, 1), "b": (5, 1), "c": (1, 1)}
    assert resolve({"a", "b", "c"}, [("a", "b")], rank) == {"a"}
