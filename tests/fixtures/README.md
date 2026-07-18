# Golden Test Fixtures

Place paired fixture files here for regression testing (no OCR required at test time).

## Creating a fixture

```bash
python -m snapfolio.cli dump-ocr path/to/screenshot.png -o tests/fixtures/my_holdings.fixture.txt
```

## Expected output

Create `my_holdings.expected.json` alongside the fixture:

```json
[
  {
    "source": "cmb_stock",
    "name": "某某股份",
    "code": "600000",
    "quantity": 1000,
    "unit_price": 10.5,
    "amount": 10500
  }
]
```

Only include fields you want to assert. The regression test compares numeric fields within 2% tolerance.
