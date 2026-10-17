from wyse.belief.core import Justif, evaluate


def J(jid, claim, *premises):
    return Justif(jid, claim, tuple(premises))


def test_alternative_branch_keeps_claim_alive():
    js = [J("j1", "c", "o1"), J("j2", "c", "o2")]
    assert evaluate({"o1", "o2"}, js)[0] == {"c"}
    assert evaluate({"o2"}, js)[0] == {"c"}
    assert evaluate(set(), js)[0] == set()


def test_joint_premises_are_all_required():
    js = [J("j1", "c", "o1", "o2")]
    assert evaluate({"o1"}, js)[0] == set()
    assert evaluate({"o1", "o2"}, js)[0] == {"c"}


def test_support_flows_through_a_chain():
    js = [J("j1", "a", "o1"), J("j2", "b", "a"), J("j3", "c", "b")]
    assert evaluate({"o1"}, js)[0] == {"a", "b", "c"}
    assert evaluate(set(), js)[0] == set()


def test_ungrounded_loop_never_supports_itself():
    js = [J("j1", "a", "b"), J("j2", "b", "a")]
    assert evaluate(set(), js)[0] == set()


def test_loop_collapses_when_its_grounding_goes():
    js = [J("j0", "a", "o1"), J("j1", "a", "b"), J("j2", "b", "a")]
    assert evaluate({"o1"}, js)[0] == {"a", "b"}
    assert evaluate(set(), js)[0] == set()


def test_justification_without_premises_is_never_valid():
    supported, valid = evaluate({"o1"}, [J("j1", "c")])
    assert supported == set()
    assert valid == set()


def test_blocked_claim_stays_out_and_starves_dependents():
    js = [J("j1", "a", "o1"), J("j2", "b", "a")]
    assert evaluate({"o1"}, js, blocked={"a"})[0] == set()


def test_unknown_premise_never_holds():
    assert evaluate({"o1"}, [J("j1", "c", "o1", "ghost")])[0] == set()


def test_repeated_premise_counts_once():
    assert evaluate({"o1"}, [J("j1", "c", "o1", "o1")])[0] == {"c"}
