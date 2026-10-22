import json
cats={"access_control","price_oracle_trust","rounding_precision","arithmetic_overflow_or_cast","input_validation","reentrancy","business_logic","signature_validation","uninitialized_or_unprotected_init","storage_collision","arbitrary_external_call","governance_design","weak_randomness","denial_of_service","other"}
L=[json.loads(l) for l in open("spike.part1.jsonl")]
assert len(L)==9
for d in L:
    assert len(d["top5"])==5 and d["confidence"] in("high","medium","low") and all(t["category"] in cats for t in d["top5"])
print("ok",len(L),sum(d["exploitable_bug_found"] for d in L))
