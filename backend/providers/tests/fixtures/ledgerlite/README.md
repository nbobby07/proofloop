# LedgerLite scanner regression source

These synthetic, deliberately isolated fixture inputs are exact text copies of
`demo_target/ledgerlite/app.py` and `reference_secure.py` from LedgerLite commit
`550a29bbfea84be36ba1a1b1ffccc2f8a2969350`. They retain their fixture labels.
Tests copy their text to a disposable approved `demo_target/ledgerlite/app.py`;
the source is scanned and never imported or executed by the provider tests.
The secure reference must be copied to that same path so the path filter alone
cannot make its scan appear clean. A clean scan is not a security verdict.
