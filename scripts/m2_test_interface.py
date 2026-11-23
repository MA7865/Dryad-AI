
from modules.vegetation.vegetation import (
    predict_vegetation
)


print("=== Test 1: Full layer ===")

full = predict_vegetation()

print("Type:", full["type"])
print("Features:", len(full["features"]))


print("\n=== Test 2: Single patch ===")

single = predict_vegetation(
    patch_ids=["P_r000_c023"]
)

print("Features:", len(single["features"]))
print(
    "Patch:",
    single["features"][0]["properties"]["patch_id"]
)


print("\n=== Test 3: Unknown patch ===")

try:
    predict_vegetation(
        patch_ids=["INVALID_PATCH"]
    )
except ValueError as error:
    print("Correctly rejected:", error)


print("\n=== Test 4: Unsupported year ===")

try:
    predict_vegetation(as_of="2024")
except ValueError as error:
    print("Correctly rejected:", error)
