-- L1 §7. One build = one file. IDs are assigned in canonical order, so equal inputs give equal files.
PRAGMA user_version = 4;  -- v4 (ADR-007): corrected_json; v3 (L2 §13): general names; v2 (L2 §11): many-to-many crops, canonical pests, compact ingredient keys
CREATE TABLE build_info      (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE source_document (id TEXT PRIMARY KEY, kind TEXT NOT NULL, url TEXT NOT NULL, sha256 TEXT NOT NULL,
                              register_date TEXT NOT NULL, pages INTEGER NOT NULL);
CREATE TABLE ingredient      (id INTEGER PRIMARY KEY, key TEXT UNIQUE NOT NULL, display TEXT NOT NULL);
CREATE TABLE ingredient_variant (variant TEXT PRIMARY KEY, canonical TEXT NOT NULL, reviewed_by TEXT NOT NULL);
CREATE TABLE product         (id INTEGER PRIMARY KEY, document_id TEXT NOT NULL REFERENCES source_document,
                              section TEXT NOT NULL, heading_raw TEXT NOT NULL, formulation TEXT,
                              parse_status TEXT NOT NULL, notes_json TEXT NOT NULL, page INTEGER NOT NULL,
                              bbox_json TEXT NOT NULL);
CREATE TABLE product_ingredient (product_id INTEGER NOT NULL REFERENCES product, position INTEGER NOT NULL,
                              ingredient_id INTEGER NOT NULL REFERENCES ingredient, conc_value REAL,
                              conc_unit TEXT, conc_basis TEXT, PRIMARY KEY (product_id, position));
CREATE TABLE crop            (id TEXT PRIMARY KEY, display_en TEXT NOT NULL, category TEXT NOT NULL);
CREATE TABLE crop_alias      (alias_key TEXT NOT NULL, lang TEXT NOT NULL, crop_id TEXT NOT NULL REFERENCES crop,
                              reviewed_by TEXT NOT NULL, PRIMARY KEY (alias_key, crop_id));
CREATE TABLE pest            (id TEXT PRIMARY KEY, display_en TEXT NOT NULL);
CREATE TABLE pest_alias      (alias_key TEXT NOT NULL, pest_id TEXT NOT NULL REFERENCES pest, reviewed_by TEXT NOT NULL,
                              PRIMARY KEY (alias_key, pest_id));
CREATE TABLE use_record      (id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES product,
                              crop_raw TEXT NOT NULL, pest_raw TEXT NOT NULL,
                              dose_ai_raw TEXT NOT NULL, dose_form_raw TEXT NOT NULL, dilution_raw TEXT NOT NULL,
                              wait_raw TEXT NOT NULL, dose_ai_json TEXT NOT NULL, dose_form_json TEXT NOT NULL,
                              dilution_json TEXT NOT NULL, wait_lo INTEGER, wait_hi INTEGER,
                              page_first INTEGER NOT NULL, page_last INTEGER NOT NULL,
                              provenance_json TEXT NOT NULL, notes_json TEXT NOT NULL,
                              corrected_json TEXT NOT NULL);  -- ADR-007: [{id, field, before}]
CREATE TABLE use_record_crop (use_record_id INTEGER NOT NULL REFERENCES use_record, crop_id TEXT NOT NULL REFERENCES crop,
                              PRIMARY KEY (use_record_id, crop_id));
CREATE TABLE use_record_pest (use_record_id INTEGER NOT NULL REFERENCES use_record, pest_id TEXT NOT NULL REFERENCES pest,
                              phrase TEXT NOT NULL, PRIMARY KEY (use_record_id, pest_id, phrase));
CREATE TABLE generic_member  (term_key TEXT NOT NULL, kind TEXT NOT NULL CHECK (kind IN ('crop', 'pest')),
                              member_id TEXT NOT NULL, PRIMARY KEY (term_key, kind, member_id));
CREATE TABLE restriction     (id INTEGER PRIMARY KEY, ingredient_key TEXT NOT NULL, name_raw TEXT NOT NULL,
                              status TEXT NOT NULL, detail_raw TEXT NOT NULL, page INTEGER NOT NULL);
CREATE TABLE anomaly         (id INTEGER PRIMARY KEY, code TEXT NOT NULL, doc_id TEXT NOT NULL, page INTEGER NOT NULL,
                              tbl INTEGER NOT NULL, row INTEGER NOT NULL, detail TEXT NOT NULL, allowed INTEGER NOT NULL);
CREATE INDEX use_by_crop    ON use_record_crop(crop_id);
CREATE INDEX use_by_product ON use_record(product_id);
CREATE INDEX pest_by_id     ON use_record_pest(pest_id);
CREATE INDEX restriction_by_key ON restriction(ingredient_key);
