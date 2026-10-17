from wyse.belief.core import Justif
from wyse.belief.independence import independent_sources, propagate_roots


def J(jid, claim, *premises):
    return Justif(jid, claim, tuple(premises))


def test_shared_origin_collapses_to_one_root():
    js = [
        J("j1", "v1", "o1"), J("j2", "v2", "o1"), J("j3", "v3", "o1"),
        J("j4", "final", "v1"), J("j5", "final", "v2"), J("j6", "final", "v3"),
    ]
    assert propagate_roots(js, {"o1"})["final"] == {"o1"}


def test_separate_origins_stay_separate():
    js = [J("j1", "a", "o1"), J("j2", "a", "o2")]
    assert propagate_roots(js, {"o1", "o2"})["a"] == {"o1", "o2"}


def test_one_source_behind_many_observations_counts_once():
    source_of = {"o1": "s1", "o2": "s1", "o3": "s2"}
    assert independent_sources({"o1", "o2"}, source_of) == {"s1"}
    assert independent_sources({"o1", "o3"}, source_of) == {"s1", "s2"}


def test_cyclic_support_terminates():
    js = [J("j1", "a", "o1"), J("j2", "a", "b"), J("j3", "b", "a")]
    roots = propagate_roots(js, {"o1"})
    assert roots["a"] == {"o1"}
    assert roots["b"] == {"o1"}
