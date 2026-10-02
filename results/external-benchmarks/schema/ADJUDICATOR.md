# Third read: deciding a field the two readers disagree on

Input: one `adjudication/queue_<study>_bNN.jsonl` file. Each line has `id`, `item` (exactly what the readers saw), `A` and `B` (each reader's values and quotes), and `open_fields` (the fields to decide). The field definitions are in the reader instructions for the study (`schema/READER-S1S3.md`, `schema/READER-S2.md`, or `schema/READER-S6.md`); read that file first.

Procedure per open field: read both readers' quotes against the definition. If one reader's quote, taken as it stands in the item text, meets the definition, decide for that reader. If neither quote decides it, read the whole item and decide from the text, supplying your own verbatim quote. A yes without a quote that meets the definition is a no.

Output: `adjudication/adj_<study>_bNN.json`, a JSON array with one object per input line: `id`, then one key per open field with the decided value, then `<field>_quote` where the field takes a quote, and `basis` (`A`, `B`, or `fresh`) and `note` (at most 25 words). Decide only the open fields. Quotes must be exact substrings of the item text.
