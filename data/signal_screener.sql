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
, first_seen_at TEXT, network_effect_strength TEXT);
INSERT INTO "companies" VALUES('ESAIY','EISAI CO LTD',NULL,NULL,NULL,NULL,NULL,'N/A',NULL,1,'yahoo_finance_search','2026-08-18','symbol and company name confirmed (score=100)',100.0,NULL,NULL,NULL,NULL,0,NULL,NULL);
INSERT INTO "companies" VALUES('VRTX','VERTEX PHARMACEUTICALS INC / MA',NULL,NULL,NULL,NULL,NULL,'N/A',NULL,1,'yahoo_finance_search','2026-08-18','symbol and company name confirmed (score=100)',100.0,NULL,NULL,NULL,NULL,0,NULL,NULL);
INSERT INTO "companies" VALUES('DAWNGBX','DAY ONE BIOPHARMACEUTICALS I',NULL,NULL,NULL,NULL,NULL,'N/A',NULL,0,'sec_edgar_submissions','2026-08-18','''Day One Biopharmaceuticals, Inc.'' (CIK 0001845337) is a real SEC filer with no active ticker or exchange currently on record — likely delisted, acquired, or taken private since this record was created',87.5,NULL,NULL,NULL,NULL,1,NULL,NULL);
INSERT INTO "companies" VALUES('ATRA','Atara Biotherapeutics, Inc.',NULL,NULL,NULL,NULL,NULL,'N/A',NULL,1,'yahoo_finance_search','2026-08-18','symbol and company name confirmed (score=100)',100.0,NULL,NULL,NULL,NULL,0,NULL,NULL);
INSERT INTO "companies" VALUES('MELI','MERCADOLIBRE INC','Nasdaq','Uruguay',NULL,NULL,'Services-Business Services, NEC','Founder-Chair','ADR',1,'yahoo_finance_search','2026-08-19','symbol and company name confirmed (score=100)',100.0,'Marcos Galperin','MercadoLibre operates an established network effect as a two-sided marketplace connecting millions of buyers and sellers across Latin America, where the value to each side increases with the participation of the other, creating strong switching costs and sustained compounding growth over multiple years.','DEF 14A:https://www.sec.gov/Archives/edgar/data/1099590/000109959026000010/meli-20260423.htm','2026-04-23',0,'2026-08-14T19:22:49.261603+00:00','Established');
INSERT INTO "companies" VALUES('SE','Sea Ltd','NYSE','Singapore',NULL,NULL,'Services-Miscellaneous Business Services','Founder-CEO','ADR',1,'yahoo_finance_search','2026-08-19','symbol and company name confirmed (score=100)',100.0,'Forrest Li','Sea Limited operates established network effects across its three core businesses: Garena (gaming platform connecting players), Shopee (two-sided e-commerce marketplace connecting buyers and sellers with demonstrated regional scale), and SeaMoney (digital financial services leveraging the user base from the other platforms).','20-F:https://www.sec.gov/Archives/edgar/data/1703399/000114036126015366/ef20067274_20f.htm','2026-04-17',0,'2026-08-14T19:23:00.918017+00:00','Established');
INSERT INTO "companies" VALUES('PDD','PDD Holdings Inc.','Nasdaq','China',NULL,NULL,'Services-Business Services, NEC','Founder-departed','ADR',1,'yahoo_finance_search','2026-08-19','symbol and company name confirmed (score=100)',100.0,'Colin Huang','PDD Holdings operates the Pinduoduo platform, an established two-sided marketplace connecting consumers and merchants in China with strong social commerce features that create switching costs and network effects that have compounded over multiple years of scaled operations.','20-F:https://www.sec.gov/Archives/edgar/data/1737806/000110465926050727/pdd-20251231x20f.htm','2026-04-29',0,'2026-08-14T19:23:08.044945+00:00','Established');
INSERT INTO "companies" VALUES('CPNG','Coupang, Inc.','NYSE','South Korea',NULL,NULL,'Retail-Catalog & Mail-Order Houses','Founder-CEO','ADR',1,'yahoo_finance_search','2026-08-19','symbol and company name confirmed (score=100)',100.0,'Bom Kim','Coupang operates an established two-sided marketplace connecting millions of customers with sellers across South Korea, where network effects have scaled over multiple years as more buyers attract more sellers and vice versa, creating switching costs through Prime-like membership benefits and same-day delivery infrastructure.','DEF 14A:https://www.sec.gov/Archives/edgar/data/1834584/000114036126017102/ny20063059x1_def14a.htm','2026-04-27',0,'2026-08-14T19:23:13.786576+00:00','Established');
INSERT INTO "companies" VALUES('GRAB','Grab Holdings Ltd','Nasdaq','Singapore',NULL,NULL,'Services-Business Services, NEC','Founder-CEO','ADR',1,'yahoo_finance_search','2026-08-19','symbol and company name confirmed (score=100)',100.0,'Anthony Tan','Grab operates an established multi-sided marketplace connecting drivers, riders, food merchants, and delivery partners across Southeast Asia, with network effects that have scaled since 2012 and create switching costs through supply-demand density in each market.','20-F:https://www.sec.gov/Archives/edgar/data/1855612/000185561226000020/ck0001855612-20251231.htm','2026-03-06',0,'2026-08-14T19:23:21.567351+00:00','Established');
INSERT INTO "companies" VALUES('ZAL.DE','ZALANDO SE','XETRA','Germany',NULL,NULL,NULL,'Founder-CEO','primary',1,'yahoo_finance_search','2026-08-19','symbol and company name confirmed (score=100) — resolved to ''ZAL.DE''',8.235294117647057987e+01,'Robert Gentz','Zalando operates an established two-sided marketplace connecting fashion brands and consumers across Europe, with network effects evident through its platform that becomes more valuable as more sellers and buyers participate.','DE:https://corporate.zalando.com/en/investor-relations/our-management-board','2026-08-19',0,'2026-08-19T21:22:01.757656+00:00','Established');
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
, first_seen_at TEXT);
INSERT INTO "designations" VALUES('e63ae8afca8ffeba','ESAIY','FDA','Breakthrough Therapy','2019-06-17','Lecanemab (Leqembi)','Early Alzheimer''s disease','NCT03887455','manual_seed:fda_breakthrough_seed.csv','2026-08-10','Eisai','Lecanemab is a treatment for early Alzheimer''s disease that received Breakthrough Therapy designation, meaning the FDA determined it may demonstrate substantial improvement over existing therapies for a serious condition. This designation matters clinically because it signals the FDA saw early evidence that the drug could meaningfully slow cognitive decline in Alzheimer''s patients, a historically difficult-to-treat neurodegenerative disease. Lecanemab represents one of the first treatments to target and clear amyloid plaques in the brain with demonstrated clinical benefit in slowing Alzheimer''s progression, compared to existing medications that primarily manage symptoms without addressing underlying disease mechanisms.','High signal','2026-08-18T14:27:25.358824+00:00',NULL,NULL);
INSERT INTO "designations" VALUES('cc178b137b0e1a6e','VRTX','FDA','Breakthrough Therapy','2021-01-28','Exagamglogene autotemcel (Casgevy)','Severe sickle cell disease','NCT03745287','manual_seed:fda_breakthrough_seed.csv','2026-08-10','Vertex Pharmaceuticals','Exagamglogene autotemcel (Casgevy) is a one-time gene therapy treatment for severe sickle cell disease that modifies a patient''s own blood stem cells to produce functional hemoglobin, potentially eliminating recurrent pain crises and reducing the need for blood transfusions. The Breakthrough Therapy designation indicates FDA recognition that early clinical evidence showed substantial improvement over existing therapies for this debilitating genetic blood disorder that disproportionately affects African American patients. Unlike chronic treatments such as hydroxyurea or regular blood transfusions that manage symptoms, this appears to be a curative gene therapy approach offering the potential for a functional cure without requiring a matched bone marrow donor, which has historically been the only curative option but is available to fewer than 20% of patients.','High signal','2026-08-18T14:27:32.320438+00:00',NULL,NULL);
INSERT INTO "designations" VALUES('c59e44d78ab40bb7','DAWNGBX','FDA','Breakthrough Therapy','2022-08-15','Tovorafenib (Ojemda)','Relapsed or progressive pediatric low-grade glioma','NCT04775485','manual_seed:fda_breakthrough_seed.csv','2026-08-10','Day One Biopharmaceuticals','Tovorafenib is being developed to treat children with low-grade gliomas (slow-growing brain tumors) that have come back or continued to grow despite treatment. The FDA''s Breakthrough Therapy designation signals that early clinical data suggest this drug may offer a substantial improvement over existing therapies for these pediatric patients who have limited effective options when their tumors progress. Traditional treatments for relapsed pediatric low-grade glioma typically involve chemotherapy regimens or additional surgery/radiation when feasible, but many children experience treatment failure or significant toxicity; a targeted therapy specifically developed for this pediatric population could offer improved tumor control with a different safety profile, though the specific mechanism and comparative efficacy data are not yet publicly detailed.','Moderate signal','2026-08-18T14:27:45.562869+00:00',NULL,NULL);
INSERT INTO "designations" VALUES('324d564d8f11bd8f','VRTX','EMA','PRIME','2020-09-22','Exagamglogene autotemcel (Casgevy)','Severe sickle cell disease','NCT03745287','manual_seed:ema_prime_seed.csv','2026-08-11','Vertex Pharmaceuticals','Exagamglogene autotemcel (Casgevy) is a one-time gene therapy treatment for severe sickle cell disease that modifies a patient''s own blood stem cells to produce functional hemoglobin, potentially eliminating recurrent pain crises and organ damage. The PRIME designation from European regulators signals this addresses a major unmet need in a serious condition where current treatments only manage symptoms rather than correct the underlying genetic defect. This represents a fundamentally different approach than existing treatments like hydroxyurea or chronic blood transfusions, as it is a one-time curative-intent gene therapy rather than lifelong symptom management, and has already received full regulatory approval in both the US and EU as the first CRISPR-based medicine.','High signal','2026-08-18T14:27:52.189347+00:00','https://www.globenewswire.com/news-release/2020/09/22/2097309/0/en/CRISPR-Therapeutics-and-Vertex-Pharmaceuticals-Announce-Priority-Medicines-PRIME-Designation-Granted-by-the-European-Medicines-Agency-EMA-to-CTX001-for-the-Treatment-of-Sickle-Cell.html',NULL);
INSERT INTO "designations" VALUES('390dfc241b225c0a','VRTX','EMA','PRIME','2021-04-26','Exagamglogene autotemcel (Casgevy)','Transfusion-dependent beta thalassemia','NCT03745287','manual_seed:ema_prime_seed.csv','2026-08-11','Vertex Pharmaceuticals','Exagamglogene autotemcel (Casgevy) is a one-time gene therapy for patients with transfusion-dependent beta thalassemia, a severe inherited blood disorder requiring lifelong regular blood transfusions. The PRIME designation from the European Medicines Agency indicates this therapy addresses a major unmet need and received accelerated assessment, reflecting its potential to free patients from the burden of chronic transfusions. Unlike standard care requiring lifelong blood transfusions every 2-4 weeks and iron chelation therapy, this represents a potentially curative one-time treatment using the patient''s own edited stem cells to restore functional hemoglobin production.','High signal','2026-08-18T14:27:57.657728+00:00','https://www.globenewswire.com/news-release/2021/04/26/2216841/0/en/Vertex-and-CRISPR-Therapeutics-Announce-Priority-Medicines-PRIME-Designation-Granted-by-the-European-Medicines-Agency-to-CTX001-for-Transfusion-Dependent-Beta-Thalassemia.html',NULL);
INSERT INTO "designations" VALUES('32bcd2fd3fa02d80','ATRA','EMA','PRIME','2016-10-01','Tabelecleucel (Ebvallo)','Epstein-Barr virus-positive post-transplant lymphoproliferative disease (EBV+ PTLD)','NCT03394365','manual_seed:ema_prime_seed.csv','2026-08-11','Atara Biotherapeutics','Tabelecleucel is a cell therapy designed to treat a rare and life-threatening cancer called post-transplant lymphoproliferative disease caused by Epstein-Barr virus, which can occur in patients after organ or stem cell transplants when their immune systems are suppressed. The PRIME designation from the European Medicines Agency signals that regulators recognize this addresses a major unmet medical need and are providing enhanced support for its development, which matters because EBV+ PTLD patients currently have very limited effective treatment options. This represents a potentially significant advance as EBV+ PTLD has no approved targeted therapies, with current treatment relying primarily on reducing immunosuppression (which risks transplant rejection) or chemotherapy regimens that are often poorly tolerated in this vulnerable patient population.','High signal','2026-08-18T14:28:04.480585+00:00','https://www.sec.gov/Archives/edgar/data/1604464/000119312517382414/d489039dex991.htm',NULL);
CREATE TABLE ownership (
    ownership_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL REFERENCES companies(ticker),
    founder_name TEXT NOT NULL,
    role TEXT NOT NULL,
    ownership_pct REAL,
    source TEXT NOT NULL,
    as_of_date TEXT NOT NULL
);
INSERT INTO "ownership" VALUES(1,'MELI','Marcos Galperin','Executive Chairman of the Board',7.0,'DEF 14A:https://www.sec.gov/Archives/edgar/data/1099590/000109959026000010/meli-20260423.htm','2026-04-23');
INSERT INTO "ownership" VALUES(2,'SE','Forrest Li','Founder and Chief Executive Officer, Chairman of the Board',16.0,'20-F:https://www.sec.gov/Archives/edgar/data/1703399/000114036126015366/ef20067274_20f.htm','2026-04-17');
INSERT INTO "ownership" VALUES(3,'PDD','Colin Huang','no active leadership role',24.8,'20-F:https://www.sec.gov/Archives/edgar/data/1737806/000110465926050727/pdd-20251231x20f.htm','2026-04-29');
INSERT INTO "ownership" VALUES(4,'CPNG','Bom Kim','Chief Executive Officer and Chairman of the Board',74.3,'DEF 14A:https://www.sec.gov/Archives/edgar/data/1834584/000114036126017102/ny20063059x1_def14a.htm','2026-04-27');
INSERT INTO "ownership" VALUES(5,'GRAB','Anthony Tan','Founder, Chairman and Chief Executive Officer',3.2,'20-F:https://www.sec.gov/Archives/edgar/data/1855612/000185561226000020/ck0001855612-20251231.htm','2026-03-06');
INSERT INTO "ownership" VALUES(6,'MELI','Marcos Galperin','Executive Chairman of the Board',7.0,'DEF 14A:https://www.sec.gov/Archives/edgar/data/1099590/000109959026000010/meli-20260423.htm','2026-04-23');
INSERT INTO "ownership" VALUES(7,'SE','Forrest Li','Founder and Chief Executive Officer, Chairman',16.0,'20-F:https://www.sec.gov/Archives/edgar/data/1703399/000114036126015366/ef20067274_20f.htm','2026-04-17');
INSERT INTO "ownership" VALUES(8,'PDD','Colin Huang','No active leadership role',24.8,'20-F:https://www.sec.gov/Archives/edgar/data/1737806/000110465926050727/pdd-20251231x20f.htm','2026-04-29');
INSERT INTO "ownership" VALUES(9,'CPNG','Bom Kim','Chief Executive Officer and Chairman of the Board',74.3,'DEF 14A:https://www.sec.gov/Archives/edgar/data/1834584/000114036126017102/ny20063059x1_def14a.htm','2026-04-27');
INSERT INTO "ownership" VALUES(10,'GRAB','Anthony Tan','Founder, Chairman and Chief Executive Officer',3.2,'20-F:https://www.sec.gov/Archives/edgar/data/1855612/000185561226000020/ck0001855612-20251231.htm','2026-03-06');
INSERT INTO "ownership" VALUES(11,'MELI','Marcos Galperin','Executive Chairman of the Board',7.0,'DEF 14A:https://www.sec.gov/Archives/edgar/data/1099590/000109959026000010/meli-20260423.htm','2026-04-23');
INSERT INTO "ownership" VALUES(12,'SE','Forrest Li','Founder and Chief Executive Officer, Chairman of Sea Limited',16.0,'20-F:https://www.sec.gov/Archives/edgar/data/1703399/000114036126015366/ef20067274_20f.htm','2026-04-17');
INSERT INTO "ownership" VALUES(13,'PDD','Colin Huang','no active leadership role',24.8,'20-F:https://www.sec.gov/Archives/edgar/data/1737806/000110465926050727/pdd-20251231x20f.htm','2026-04-29');
INSERT INTO "ownership" VALUES(14,'CPNG','Bom Kim','Founder, Chief Executive Officer and Chairman of the Board',74.3,'DEF 14A:https://www.sec.gov/Archives/edgar/data/1834584/000114036126017102/ny20063059x1_def14a.htm','2026-04-27');
INSERT INTO "ownership" VALUES(15,'GRAB','Anthony Tan','Founder, Chairman and Chief Executive Officer',3.2,'20-F:https://www.sec.gov/Archives/edgar/data/1855612/000185561226000020/ck0001855612-20251231.htm','2026-03-06');
INSERT INTO "ownership" VALUES(16,'MELI','Marcos Galperin','Executive Chairman of the Board',7.0,'DEF 14A:https://www.sec.gov/Archives/edgar/data/1099590/000109959026000010/meli-20260423.htm','2026-04-23');
INSERT INTO "ownership" VALUES(17,'SE','Forrest Li','Founder and Chief Executive Officer, Chairman of Sea Limited',16.0,'20-F:https://www.sec.gov/Archives/edgar/data/1703399/000114036126015366/ef20067274_20f.htm','2026-04-17');
INSERT INTO "ownership" VALUES(18,'PDD','Colin Huang','no active leadership role',24.8,'20-F:https://www.sec.gov/Archives/edgar/data/1737806/000110465926050727/pdd-20251231x20f.htm','2026-04-29');
INSERT INTO "ownership" VALUES(19,'CPNG','Bom Kim','Founder, Chief Executive Officer and Chairman of the Board',74.3,'DEF 14A:https://www.sec.gov/Archives/edgar/data/1834584/000114036126017102/ny20063059x1_def14a.htm','2026-04-27');
INSERT INTO "ownership" VALUES(20,'GRAB','Anthony Tan','Founder, Chairman and Chief Executive Officer',3.2,'20-F:https://www.sec.gov/Archives/edgar/data/1855612/000185561226000020/ck0001855612-20251231.htm','2026-03-06');
INSERT INTO "ownership" VALUES(21,'MELI','Marcos Galperin','Executive Chairman of the Board',7.0,'DEF 14A:https://www.sec.gov/Archives/edgar/data/1099590/000109959026000010/meli-20260423.htm','2026-04-23');
INSERT INTO "ownership" VALUES(22,'SE','Forrest Li','Founder and Chief Executive Officer, Chairman of Sea Limited',16.0,'20-F:https://www.sec.gov/Archives/edgar/data/1703399/000114036126015366/ef20067274_20f.htm','2026-04-17');
INSERT INTO "ownership" VALUES(23,'PDD','Colin Huang','No active leadership role',24.8,'20-F:https://www.sec.gov/Archives/edgar/data/1737806/000110465926050727/pdd-20251231x20f.htm','2026-04-29');
INSERT INTO "ownership" VALUES(24,'CPNG','Bom Kim','Chief Executive Officer and Chairman of the Board',74.3,'DEF 14A:https://www.sec.gov/Archives/edgar/data/1834584/000114036126017102/ny20063059x1_def14a.htm','2026-04-27');
INSERT INTO "ownership" VALUES(25,'GRAB','Anthony Tan','Founder, Chairman and Chief Executive Officer',3.2,'20-F:https://www.sec.gov/Archives/edgar/data/1855612/000185561226000020/ck0001855612-20251231.htm','2026-03-06');
INSERT INTO "ownership" VALUES(26,'ZAL.DE','Robert Gentz','Co-founder and co-CEO',NULL,'DE:https://corporate.zalando.com/en/investor-relations/our-management-board','2026-08-19');
CREATE TABLE site_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_generated_at TEXT
);
INSERT INTO "site_state" VALUES(1,'2026-08-20T13:41:45.597928+00:00');
CREATE TABLE tracked_outcomes (
    outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id TEXT NOT NULL UNIQUE,
    entry_type TEXT NOT NULL,  -- "designation" | "founder_stock"
    ticker TEXT NOT NULL,
    date_flagged TEXT NOT NULL,
    flag_given TEXT NOT NULL,  -- "High signal" | "Moderate signal"
    price_source TEXT,
    price_at_flag REAL,
    price_at_flag_date TEXT,
    check_3mo_due TEXT NOT NULL,
    price_at_3mo REAL,
    price_at_3mo_date TEXT,
    check_6mo_due TEXT NOT NULL,
    price_at_6mo REAL,
    price_at_6mo_date TEXT,
    check_12mo_due TEXT NOT NULL,
    price_at_12mo REAL,
    price_at_12mo_date TEXT,
    notes_on_outcome TEXT
);
INSERT INTO "tracked_outcomes" VALUES(1,'e63ae8afca8ffeba','designation','ESAIY','2026-08-17','High signal','yahoo_finance_chart',7.4,'2026-08-17','2026-11-17',NULL,NULL,'2027-02-17',NULL,NULL,'2027-08-17',NULL,NULL,NULL);
INSERT INTO "tracked_outcomes" VALUES(2,'cc178b137b0e1a6e','designation','VRTX','2026-08-17','High signal','yahoo_finance_chart',515.55,'2026-08-17','2026-11-17',NULL,NULL,'2027-02-17',NULL,NULL,'2027-08-17',NULL,NULL,NULL);
INSERT INTO "tracked_outcomes" VALUES(3,'c59e44d78ab40bb7','designation','DAWNGBX','2026-08-17','High signal',NULL,NULL,NULL,'2026-11-17',NULL,NULL,'2027-02-17',NULL,NULL,'2027-08-17',NULL,NULL,'Price at flag unavailable — fetch failed when this entry was flagged.');
INSERT INTO "tracked_outcomes" VALUES(4,'324d564d8f11bd8f','designation','VRTX','2026-08-17','High signal','yahoo_finance_chart',515.55,'2026-08-17','2026-11-17',NULL,NULL,'2027-02-17',NULL,NULL,'2027-08-17',NULL,NULL,NULL);
INSERT INTO "tracked_outcomes" VALUES(5,'390dfc241b225c0a','designation','VRTX','2026-08-17','High signal','yahoo_finance_chart',515.55,'2026-08-17','2026-11-17',NULL,NULL,'2027-02-17',NULL,NULL,'2027-08-17',NULL,NULL,NULL);
INSERT INTO "tracked_outcomes" VALUES(6,'32bcd2fd3fa02d80','designation','ATRA','2026-08-17','High signal','yahoo_finance_chart',8.36,'2026-08-17','2026-11-17',NULL,NULL,'2027-02-17',NULL,NULL,'2027-08-17',NULL,NULL,NULL);
INSERT INTO "tracked_outcomes" VALUES(7,'MELI','founder_stock','MELI','2026-08-18','Moderate signal','yahoo_finance_chart',1766.475,'2026-08-18','2026-11-18',NULL,NULL,'2027-02-18',NULL,NULL,'2027-08-18',NULL,NULL,NULL);
INSERT INTO "tracked_outcomes" VALUES(8,'SE','founder_stock','SE','2026-08-18','High signal','yahoo_finance_chart',115.59,'2026-08-18','2026-11-18',NULL,NULL,'2027-02-18',NULL,NULL,'2027-08-18',NULL,NULL,NULL);
INSERT INTO "tracked_outcomes" VALUES(9,'CPNG','founder_stock','CPNG','2026-08-18','High signal','yahoo_finance_chart',15.685,'2026-08-18','2026-11-18',NULL,NULL,'2027-02-18',NULL,NULL,'2027-08-18',NULL,NULL,NULL);
INSERT INTO "tracked_outcomes" VALUES(10,'GRAB','founder_stock','GRAB','2026-08-18','High signal','yahoo_finance_chart',3.499,'2026-08-18','2026-11-18',NULL,NULL,'2027-02-18',NULL,NULL,'2027-08-18',NULL,NULL,NULL);
INSERT INTO "tracked_outcomes" VALUES(11,'ZAL.DE','founder_stock','ZAL.DE','2026-08-19','High signal','yahoo_finance_chart',22.56,'2026-08-19','2026-11-19',NULL,NULL,'2027-02-19',NULL,NULL,'2027-08-19',NULL,NULL,NULL);
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
INSERT INTO "trials" VALUES('NCT03887455','ClinicalTrials.gov','PHASE3','ACTIVE_NOT_RECRUITING','2019-03-27','2029-06-30','Early Alzheimer''s Disease','2026-08-18T14:27:20.314272+00:00');
INSERT INTO "trials" VALUES('NCT03745287','ClinicalTrials.gov','PHASE2, PHASE3','COMPLETED','2018-11-27','2025-07-07','Sickle Cell Disease; Hematological Diseases; Hemoglobinopathies','2026-08-18T14:27:52.905321+00:00');
INSERT INTO "trials" VALUES('NCT04775485','ClinicalTrials.gov','PHASE2','RECRUITING','2021-04-22','2027-05-31','Low-grade Glioma; Advanced Solid Tumor','2026-08-18T14:27:39.303669+00:00');
INSERT INTO "trials" VALUES('NCT03394365','ClinicalTrials.gov','PHASE3','RECRUITING','2017-12-29','2030-05-31','Epstein-Barr Virus+ Associated Post-transplant Lymphoproliferative Disease (EBV+ PTLD); Solid Organ Transplant Complications; Lymphoproliferative Disorders; Allogeneic Hematopoietic Cell Transplant; Stem Cell Transplant Complications','2026-08-18T14:27:58.263528+00:00');
CREATE TABLE user_notes (
    note_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id TEXT NOT NULL,
    date_written TEXT NOT NULL,
    note_text TEXT NOT NULL
);
INSERT INTO "user_notes" VALUES(1,'cc178b137b0e1a6e','2026-08-14','First real CRISPR therapy approval - worth tracking how the pricing/reimbursement story plays out.');
INSERT INTO "user_notes" VALUES(3,'ZAL.DE','2026-08-19','ownership_pct unavailable for both Zalando co-founders (Robert Gentz, David Schneider): the only source disclosing their combined stake (~5%) is a PNG chart on corporate.zalando.com/en/investor-relations/shareholder-structure, not machine-readable text this pipeline can extract. BaFin''s WpHG voting-rights database has nothing on file for either individually (both below the 3% mandatory disclosure threshold). CONSEQUENCE: if either founder''s leadership status changes (e.g. steps back from CEO to Chairman), the automated Founder-Chair vs. Founder-departed classification cannot verify the required >5% ownership threshold from any scraped source. Check the shareholder-structure page manually before trusting that classification.');
DELETE FROM "sqlite_sequence";
INSERT INTO "sqlite_sequence" VALUES('user_notes',3);
INSERT INTO "sqlite_sequence" VALUES('ownership',26);
INSERT INTO "sqlite_sequence" VALUES('tracked_outcomes',11);
COMMIT;
