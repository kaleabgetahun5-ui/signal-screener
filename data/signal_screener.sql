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
INSERT INTO "companies" VALUES('ESAIY','EISAI CO LTD',NULL,NULL,NULL,NULL,NULL,'N/A',NULL,1,'yahoo_finance_search','2026-08-14','symbol and company name confirmed (score=100)',100.0,NULL,NULL,NULL,NULL,0);
INSERT INTO "companies" VALUES('VRTX','VERTEX PHARMACEUTICALS INC / MA',NULL,NULL,NULL,NULL,NULL,'N/A',NULL,1,'yahoo_finance_search','2026-08-14','symbol and company name confirmed (score=100)',100.0,NULL,NULL,NULL,NULL,0);
INSERT INTO "companies" VALUES('DAWNGBX','DAY ONE BIOPHARMACEUTICALS I',NULL,NULL,NULL,NULL,NULL,'N/A',NULL,0,'sec_edgar_submissions','2026-08-14','''Day One Biopharmaceuticals, Inc.'' (CIK 0001845337) is a real SEC filer with no active ticker or exchange currently on record — likely delisted, acquired, or taken private since this record was created',87.5,NULL,NULL,NULL,NULL,1);
INSERT INTO "companies" VALUES('ATRA','Atara Biotherapeutics, Inc.',NULL,NULL,NULL,NULL,NULL,'N/A',NULL,1,'yahoo_finance_search','2026-08-14','symbol and company name confirmed (score=100)',100.0,NULL,NULL,NULL,NULL,0);
INSERT INTO "companies" VALUES('MELI','MERCADOLIBRE INC','Nasdaq','Uruguay',NULL,NULL,'Services-Business Services, NEC','Founder-Chair','ADR',1,'yahoo_finance_search','2026-08-14','symbol and company name confirmed (score=100)',100.0,'Marcos Galperin','More buyers attract more sellers and vice versa on the marketplace; more users in the fintech ecosystem increase the value and utility of payment and financial services for all participants.','DEF 14A:https://www.sec.gov/Archives/edgar/data/1099590/000109959026000010/meli-20260423.htm','2026-04-23',0);
INSERT INTO "companies" VALUES('SE','Sea Ltd','NYSE','Singapore',NULL,NULL,'Services-Miscellaneous Business Services','Founder-CEO','ADR',1,'yahoo_finance_search','2026-08-14','symbol and company name confirmed (score=100)',100.0,'Forrest Li','Sea Limited operates multiple network effects across its ecosystem: Shopee''s e-commerce marketplace benefits from more buyers attracting more sellers and vice versa; Garena''s gaming platform creates network effects where more players make games more engaging and valuable for each user; and SeaMoney''s digital financial services benefit from increased merchant and user adoption creating a more useful payment network.','20-F:https://www.sec.gov/Archives/edgar/data/1703399/000114036126015366/ef20067274_20f.htm','2026-04-17',0);
INSERT INTO "companies" VALUES('PDD','PDD Holdings Inc.','Nasdaq','China',NULL,NULL,'Services-Business Services, NEC','Founder-departed','ADR',1,'yahoo_finance_search','2026-08-14','symbol and company name confirmed (score=100)',100.0,'Colin Huang','More buyers attract more sellers/merchants to the platform, which in turn attracts more buyers seeking better prices and selection through group-buying dynamics','20-F:https://www.sec.gov/Archives/edgar/data/1737806/000110465926050727/pdd-20251231x20f.htm','2026-04-29',0);
INSERT INTO "companies" VALUES('CPNG','Coupang, Inc.','NYSE','South Korea',NULL,NULL,'Retail-Catalog & Mail-Order Houses','Founder-CEO','ADR',1,'yahoo_finance_search','2026-08-14','symbol and company name confirmed (score=100)',100.0,'Bom Kim','More suppliers and merchants on the platform attract more customers, which in turn attracts more suppliers, creating a two-sided marketplace network effect.','DEF 14A:https://www.sec.gov/Archives/edgar/data/1834584/000114036126017102/ny20063059x1_def14a.htm','2026-04-27',0);
INSERT INTO "companies" VALUES('GRAB','Grab Holdings Ltd','Nasdaq','Singapore',NULL,NULL,'Services-Business Services, NEC','Founder-CEO','ADR',1,'yahoo_finance_search','2026-08-14','symbol and company name confirmed (score=100)',100.0,'Anthony Tan','More drivers attract more riders due to shorter wait times, while more riders attract more drivers due to higher earning potential, creating a two-sided marketplace network effect; additionally, more merchant partners enhance delivery selection for consumers while more consumers attract more merchants.','20-F:https://www.sec.gov/Archives/edgar/data/1855612/000185561226000020/ck0001855612-20251231.htm','2026-03-06',0);
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
INSERT INTO "designations" VALUES('e63ae8afca8ffeba','ESAIY','FDA','Breakthrough Therapy','2019-06-17','Lecanemab (Leqembi)','Early Alzheimer''s disease','NCT03887455','manual_seed:fda_breakthrough_seed.csv','2026-08-10','Eisai','Lecanemab is a treatment for early Alzheimer''s disease that received Breakthrough Therapy designation, meaning the FDA determined it shows substantial improvement over existing therapies for a serious condition. The designation matters clinically because it indicates early evidence suggested Lecanemab could meaningfully slow cognitive decline in early-stage patients, addressing an area of major unmet medical need. Lecanemab is one of the first treatments to demonstrate actual disease modification in Alzheimer''s rather than just symptom management, distinguishing it from older medications like donepezil that only temporarily improve symptoms without slowing disease progression.','High signal','2026-08-14T16:19:38.144146+00:00',NULL);
INSERT INTO "designations" VALUES('cc178b137b0e1a6e','VRTX','FDA','Breakthrough Therapy','2021-01-28','Exagamglogene autotemcel (Casgevy)','Severe sickle cell disease','NCT03745287','manual_seed:fda_breakthrough_seed.csv','2026-08-10','Vertex Pharmaceuticals','Exagamglogene autotemcel (Casgevy) is a one-time gene therapy treatment designed to enable patients with severe sickle cell disease to produce healthy red blood cells, potentially eliminating painful vaso-occlusive crises and reducing the need for blood transfusions. The Breakthrough Therapy designation from the FDA signals that early clinical evidence showed this treatment may offer substantial improvement over existing therapies for a serious, life-threatening condition. Unlike existing treatments for sickle cell disease that require lifelong medication or repeated blood transfusions to manage symptoms, this represents a potential one-time curative approach using the patient''s own genetically modified cells to address the underlying cause of the disease.','High signal','2026-08-14T16:19:42.999541+00:00',NULL);
INSERT INTO "designations" VALUES('c59e44d78ab40bb7','DAWNGBX','FDA','Breakthrough Therapy','2022-08-15','Tovorafenib (Ojemda)','Relapsed or progressive pediatric low-grade glioma','NCT04775485','manual_seed:fda_breakthrough_seed.csv','2026-08-10','Day One Biopharmaceuticals','Tovorafenib is being developed to treat children with low-grade gliomas (slow-growing brain tumors) that have come back or continued to grow despite prior treatment. The FDA''s Breakthrough Therapy designation in 2022 indicates that early clinical data showed this drug may offer a substantial improvement over existing options for these pediatric patients who have limited alternatives after their tumors progress. For relapsed pediatric low-grade glioma, standard options are limited and often involve repeat surgery, radiation (which has long-term developmental risks in children), or chemotherapy regimens with variable success rates, making a targeted oral therapy potentially meaningful if it demonstrates durable tumor control with manageable toxicity.','High signal','2026-08-14T16:19:53.643114+00:00',NULL);
INSERT INTO "designations" VALUES('324d564d8f11bd8f','VRTX','EMA','PRIME','2020-09-22','Exagamglogene autotemcel (Casgevy)','Severe sickle cell disease','NCT03745287','manual_seed:ema_prime_seed.csv','2026-08-11','Vertex Pharmaceuticals','Exagamglogene autotemcel (Casgevy) is a one-time gene therapy that modifies a patient''s own blood stem cells to produce functional hemoglobin, potentially eliminating the painful vaso-occlusive crises and organ damage that define severe sickle cell disease. The PRIME designation from the EMA signals that regulators recognized this as addressing a critical unmet need with potential major therapeutic advantage, expediting its development review. Unlike chronic treatments that manage symptoms (hydroxyurea, blood transfusions, pain medications) or the recently approved gene therapies requiring chemotherapy conditioning, this represents a curative approach using CRISPR gene-editing technology to address the root genetic cause of sickle cell disease with completed Phase 2/3 trials showing durable responses.','High signal','2026-08-14T16:19:59.668141+00:00','https://www.globenewswire.com/news-release/2020/09/22/2097309/0/en/CRISPR-Therapeutics-and-Vertex-Pharmaceuticals-Announce-Priority-Medicines-PRIME-Designation-Granted-by-the-European-Medicines-Agency-EMA-to-CTX001-for-the-Treatment-of-Sickle-Cell.html');
INSERT INTO "designations" VALUES('390dfc241b225c0a','VRTX','EMA','PRIME','2021-04-26','Exagamglogene autotemcel (Casgevy)','Transfusion-dependent beta thalassemia','NCT03745287','manual_seed:ema_prime_seed.csv','2026-08-11','Vertex Pharmaceuticals','Exagamglogene autotemcel (Casgevy) is a one-time gene therapy for patients with transfusion-dependent beta thalassemia, a severe inherited blood disorder requiring regular lifelong blood transfusions to survive. The PRIME designation from the European Medicines Agency indicates this therapy addresses a major unmet medical need by potentially eliminating the need for chronic transfusions and their associated complications including iron overload and organ damage. This represents a curative gene-editing approach using CRISPR technology that modifies patients'' own stem cells to restore functional hemoglobin production, fundamentally different from chronic supportive care with transfusions and iron chelation or even allogeneic bone marrow transplants that require matched donors and carry rejection risks.','High signal','2026-08-14T16:20:04.960678+00:00','https://www.globenewswire.com/news-release/2021/04/26/2216841/0/en/Vertex-and-CRISPR-Therapeutics-Announce-Priority-Medicines-PRIME-Designation-Granted-by-the-European-Medicines-Agency-to-CTX001-for-Transfusion-Dependent-Beta-Thalassemia.html');
INSERT INTO "designations" VALUES('32bcd2fd3fa02d80','ATRA','EMA','PRIME','2016-10-01','Tabelecleucel (Ebvallo)','Epstein-Barr virus-positive post-transplant lymphoproliferative disease (EBV+ PTLD)','NCT03394365','manual_seed:ema_prime_seed.csv','2026-08-11','Atara Biotherapeutics','Tabelecleucel is a cell therapy designed to treat a dangerous cancer called post-transplant lymphoproliferative disease that occurs in some organ transplant recipients when Epstein-Barr virus causes uncontrolled growth of immune cells. The PRIME designation from European regulators indicates this addresses a major unmet medical need where few effective treatment options currently exist, potentially offering these high-risk transplant patients a targeted therapy when their weakened immune systems cannot control the virus-driven cancer on their own. This represents a targeted cellular immunotherapy approach for EBV+ PTLD, a condition where standard chemotherapy often fails and treatment options are extremely limited, particularly for patients who don''t respond to initial reduction of immunosuppression or rituximab.','High signal','2026-08-14T16:20:11.274412+00:00','https://www.sec.gov/Archives/edgar/data/1604464/000119312517382414/d489039dex991.htm');
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
INSERT INTO "ownership" VALUES(2,'SE','Forrest Li','Founder Forrest Xiaodong Li serves as Chairman and Chief Executive Officer',16.0,'20-F:https://www.sec.gov/Archives/edgar/data/1703399/000114036126015366/ef20067274_20f.htm','2026-04-17');
INSERT INTO "ownership" VALUES(3,'PDD','Colin Huang','No active leadership role - Zheng Huang is not listed among directors and executive officers',24.8,'20-F:https://www.sec.gov/Archives/edgar/data/1737806/000110465926050727/pdd-20251231x20f.htm','2026-04-29');
INSERT INTO "ownership" VALUES(4,'CPNG','Bom Kim','Chief Executive Officer and Chairman of the Board',74.3,'DEF 14A:https://www.sec.gov/Archives/edgar/data/1834584/000114036126017102/ny20063059x1_def14a.htm','2026-04-27');
INSERT INTO "ownership" VALUES(5,'GRAB','Anthony Tan','Founder, Chairman and Chief Executive Officer',3.2,'20-F:https://www.sec.gov/Archives/edgar/data/1855612/000185561226000020/ck0001855612-20251231.htm','2026-03-06');
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
INSERT INTO "trials" VALUES('NCT03887455','ClinicalTrials.gov','PHASE3','ACTIVE_NOT_RECRUITING','2019-03-27','2029-06-30','Early Alzheimer''s Disease','2026-08-14T16:19:33.497361+00:00');
INSERT INTO "trials" VALUES('NCT03745287','ClinicalTrials.gov','PHASE2, PHASE3','COMPLETED','2018-11-27','2025-07-07','Sickle Cell Disease; Hematological Diseases; Hemoglobinopathies','2026-08-14T16:20:00.038711+00:00');
INSERT INTO "trials" VALUES('NCT04775485','ClinicalTrials.gov','PHASE2','RECRUITING','2021-04-22','2027-05-31','Low-grade Glioma; Advanced Solid Tumor','2026-08-14T16:19:47.868738+00:00');
INSERT INTO "trials" VALUES('NCT03394365','ClinicalTrials.gov','PHASE3','RECRUITING','2017-12-29','2030-05-31','Epstein-Barr Virus+ Associated Post-transplant Lymphoproliferative Disease (EBV+ PTLD); Solid Organ Transplant Complications; Lymphoproliferative Disorders; Allogeneic Hematopoietic Cell Transplant; Stem Cell Transplant Complications','2026-08-14T16:20:05.410966+00:00');
DELETE FROM "sqlite_sequence";
INSERT INTO "sqlite_sequence" VALUES('ownership',5);
COMMIT;
