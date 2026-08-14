BEGIN TRANSACTION;
CREATE TABLE companies (
    ticker TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    exchange TEXT,
    country TEXT,
    market_cap REAL,
    currency TEXT,
    sector TEXT,
    founder_tier TEXT DEFAULT 'N/A',
    listing_type TEXT,
    ticker_verified INTEGER NOT NULL DEFAULT 0,
    ticker_verification_source TEXT,
    ticker_verification_date TEXT,
    ticker_verification_reason TEXT,
    ticker_match_confidence REAL,
    founder_name TEXT,
    network_effect TEXT,
    founder_tier_source TEXT,
    founder_tier_as_of_date TEXT,
    -- Brief section 4's "listing status changed" case — see models.py's
    -- Company.delisted_or_acquired.
    delisted_or_acquired INTEGER NOT NULL DEFAULT 0
);
INSERT INTO "companies" VALUES('ESAIY','EISAI CO LTD',NULL,NULL,NULL,NULL,NULL,'N/A',NULL,1,'yahoo_finance_search','2026-08-13','symbol and company name confirmed (score=100)',100.0,NULL,NULL,NULL,NULL,0);
INSERT INTO "companies" VALUES('VRTX','VERTEX PHARMACEUTICALS INC / MA',NULL,NULL,NULL,NULL,NULL,'N/A',NULL,1,'yahoo_finance_search','2026-08-13','symbol and company name confirmed (score=100)',100.0,NULL,NULL,NULL,NULL,0);
INSERT INTO "companies" VALUES('DAWNGBX','DAY ONE BIOPHARMACEUTICALS I',NULL,NULL,NULL,NULL,NULL,'N/A',NULL,0,'sec_edgar_submissions','2026-08-13','''Day One Biopharmaceuticals, Inc.'' (CIK 0001845337) is a real SEC filer with no active ticker or exchange currently on record — likely delisted, acquired, or taken private since this record was created',87.5,NULL,NULL,NULL,NULL,1);
INSERT INTO "companies" VALUES('ATRA','Atara Biotherapeutics, Inc.',NULL,NULL,NULL,NULL,NULL,'N/A',NULL,1,'yahoo_finance_search','2026-08-13','symbol and company name confirmed (score=100)',100.0,NULL,NULL,NULL,NULL,0);
CREATE TABLE designations (
    designation_id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL REFERENCES companies(ticker),
    source TEXT NOT NULL,
    type TEXT NOT NULL,
    date_granted TEXT NOT NULL,
    drug_name TEXT NOT NULL,
    indication TEXT,
    trial_id TEXT,
    data_source TEXT NOT NULL,
    data_as_of_date TEXT NOT NULL,
    -- Company name as it appeared in the source, before ticker matching.
    -- Kept separately from companies.company_name because that field
    -- reflects whatever the matcher resolved to (right or wrong) — for a
    -- failed/unverified match, companies.company_name can be a genuinely
    -- different, wrong company (e.g. "Eisai" matched to "Hesai Group").
    -- Display code should show this field, not the resolved one, whenever
    -- ticker_verified is false.
    raw_company_name TEXT NOT NULL,
    summary_text TEXT,
    summary_confidence_flag TEXT,
    summary_generated_at TEXT,
    -- Citation for date_granted specifically (a press release/filing URL),
    -- not just data_source's "manual_seed:<file>" — see models.py.
    date_granted_source TEXT
);
INSERT INTO "designations" VALUES('e63ae8afca8ffeba','ESAIY','FDA','Breakthrough Therapy','2019-06-17','Lecanemab (Leqembi)','Early Alzheimer''s disease','NCT03887455','manual_seed:fda_breakthrough_seed.csv','2026-08-10','Eisai',NULL,NULL,NULL,NULL);
INSERT INTO "designations" VALUES('cc178b137b0e1a6e','VRTX','FDA','Breakthrough Therapy','2021-01-28','Exagamglogene autotemcel (Casgevy)','Severe sickle cell disease','NCT03745287','manual_seed:fda_breakthrough_seed.csv','2026-08-10','Vertex Pharmaceuticals',NULL,NULL,NULL,NULL);
INSERT INTO "designations" VALUES('c59e44d78ab40bb7','DAWNGBX','FDA','Breakthrough Therapy','2022-08-15','Tovorafenib (Ojemda)','Relapsed or progressive pediatric low-grade glioma','NCT04775485','manual_seed:fda_breakthrough_seed.csv','2026-08-10','Day One Biopharmaceuticals',NULL,NULL,NULL,NULL);
INSERT INTO "designations" VALUES('324d564d8f11bd8f','VRTX','EMA','PRIME','2020-09-22','Exagamglogene autotemcel (Casgevy)','Severe sickle cell disease','NCT03745287','manual_seed:ema_prime_seed.csv','2026-08-11','Vertex Pharmaceuticals',NULL,NULL,NULL,'https://www.globenewswire.com/news-release/2020/09/22/2097309/0/en/CRISPR-Therapeutics-and-Vertex-Pharmaceuticals-Announce-Priority-Medicines-PRIME-Designation-Granted-by-the-European-Medicines-Agency-EMA-to-CTX001-for-the-Treatment-of-Sickle-Cell.html');
INSERT INTO "designations" VALUES('390dfc241b225c0a','VRTX','EMA','PRIME','2021-04-26','Exagamglogene autotemcel (Casgevy)','Transfusion-dependent beta thalassemia','NCT03745287','manual_seed:ema_prime_seed.csv','2026-08-11','Vertex Pharmaceuticals',NULL,NULL,NULL,'https://www.globenewswire.com/news-release/2021/04/26/2216841/0/en/Vertex-and-CRISPR-Therapeutics-Announce-Priority-Medicines-PRIME-Designation-Granted-by-the-European-Medicines-Agency-to-CTX001-for-Transfusion-Dependent-Beta-Thalassemia.html');
INSERT INTO "designations" VALUES('32bcd2fd3fa02d80','ATRA','EMA','PRIME','2016-10-01','Tabelecleucel (Ebvallo)','Epstein-Barr virus-positive post-transplant lymphoproliferative disease (EBV+ PTLD)','NCT03394365','manual_seed:ema_prime_seed.csv','2026-08-11','Atara Biotherapeutics',NULL,NULL,NULL,'https://www.sec.gov/Archives/edgar/data/1604464/000119312517382414/d489039dex991.htm');
CREATE TABLE ownership (
    ownership_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL REFERENCES companies(ticker),
    founder_name TEXT NOT NULL,
    role TEXT NOT NULL,
    ownership_pct REAL,
    source TEXT NOT NULL,
    as_of_date TEXT NOT NULL
);
CREATE TABLE trials (
    trial_id TEXT PRIMARY KEY,
    registry TEXT NOT NULL,
    phase TEXT,
    status TEXT,
    start_date TEXT,
    primary_completion_date TEXT,
    condition TEXT,
    fetched_at TEXT NOT NULL
);
INSERT INTO "trials" VALUES('NCT03887455','ClinicalTrials.gov','PHASE3','ACTIVE_NOT_RECRUITING','2019-03-27','2029-06-30','Early Alzheimer''s Disease','2026-08-13T23:57:32.470301+00:00');
INSERT INTO "trials" VALUES('NCT03745287','ClinicalTrials.gov','PHASE2, PHASE3','COMPLETED','2018-11-27','2025-07-07','Sickle Cell Disease; Hematological Diseases; Hemoglobinopathies','2026-08-13T23:57:40.648480+00:00');
INSERT INTO "trials" VALUES('NCT04775485','ClinicalTrials.gov','PHASE2','RECRUITING','2021-04-22','2027-05-31','Low-grade Glioma; Advanced Solid Tumor','2026-08-13T23:57:39.846683+00:00');
INSERT INTO "trials" VALUES('NCT03394365','ClinicalTrials.gov','PHASE3','RECRUITING','2017-12-29','2030-05-31','Epstein-Barr Virus+ Associated Post-transplant Lymphoproliferative Disease (EBV+ PTLD); Solid Organ Transplant Complications; Lymphoproliferative Disorders; Allogeneic Hematopoietic Cell Transplant; Stem Cell Transplant Complications','2026-08-13T23:57:41.109727+00:00');
DELETE FROM "sqlite_sequence";
COMMIT;
