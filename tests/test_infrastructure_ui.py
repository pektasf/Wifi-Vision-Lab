import pandas as pd

from scripts.infrastructure_ui import assign_identity_keys


def test_assign_identity_keys_handles_mixed_and_missing_ip_mac():
    source = pd.DataFrame(
        [
            {"ip": "192.168.1.10", "mac": "aa:bb:cc:dd:ee:10"},
            {"ip": "", "mac": "aa:bb:cc:dd:ee:20"},
            {"ip": "", "mac": ""},
            {"ip": "", "mac": ""},
        ],
        index=[0, 1, 2, 3],
    )

    result = assign_identity_keys(source, "ip", "mac")

    assert result["_identity"].tolist() == [
        "192.168.1.10",
        "AA:BB:CC:DD:EE:20",
        "kayit-2",
        "kayit-3",
    ]
    assert result["_identity"].is_unique
