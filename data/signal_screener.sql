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
, first_seen_at TEXT, network_effect_strength TEXT, trailing_pe REAL, forward_pe REAL, fifty_two_week_low REAL, fifty_two_week_high REAL, beta REAL, dividend_yield_pct REAL, valuation_as_of_date TEXT, valuation_source TEXT, ipo_date TEXT, ipo_price REAL, backtest_current_price REAL, sp500_price_at_ipo REAL, sp500_current_price REAL, backtest_as_of_date TEXT, backtest_source TEXT, founder_extraction_fingerprint TEXT, founder_transition_date TEXT);
INSERT INTO "companies" VALUES('ESAIY','EISAI CO LTD',NULL,NULL,NULL,NULL,NULL,'N/A',NULL,1,'yahoo_finance_search','2026-09-01','symbol and company name confirmed (score=100)',100.0,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "companies" VALUES('VRTX','VERTEX PHARMACEUTICALS INC / MA',NULL,NULL,NULL,NULL,NULL,'N/A',NULL,1,'yahoo_finance_search','2026-09-01','symbol and company name confirmed (score=100)',100.0,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "companies" VALUES('DAWNGBX','DAY ONE BIOPHARMACEUTICALS I',NULL,NULL,NULL,NULL,NULL,'N/A',NULL,0,'sec_edgar_submissions','2026-09-01','''Day One Biopharmaceuticals, Inc.'' (CIK 0001845337) is a real SEC filer with no active ticker or exchange currently on record — likely delisted, acquired, or taken private since this record was created',87.5,NULL,NULL,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "companies" VALUES('ATRA','Atara Biotherapeutics, Inc.',NULL,NULL,NULL,NULL,NULL,'N/A',NULL,1,'yahoo_finance_search','2026-09-01','symbol and company name confirmed (score=100)',100.0,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "companies" VALUES('MELI','MERCADOLIBRE INC','Nasdaq','Uruguay',98159140864.0,'USD','Services-Business Services, NEC','Founder-Chair','ADR',1,'yahoo_finance_search','2026-09-01','symbol and company name confirmed (score=100)',100.0,'Marcos Galperin','MercadoLibre operates an established two-sided marketplace connecting millions of buyers and sellers across Latin America, with strong network effects where more buyers attract more sellers and vice versa, reinforced by integrated fintech services (Mercado Pago) and logistics infrastructure that create significant switching costs and barriers to entry.','DEF 14A:https://www.sec.gov/Archives/edgar/data/1099590/000109959026000010/meli-20260423.htm','2026-04-23',0,'2026-08-14T19:22:49.261603+00:00','Established',52.657055,34.069386,1495.0,2548.5,1.312,NULL,'2026-09-01','yahoo_finance_quotesummary','2007-08-10',28.5,1936.2,1.4536400146484375e+03,7686.14,'2026-09-01','yahoo_finance_chart','1c2c9dbc5a9ae118b9025236f756139a964bfb69','2026-01-01');
INSERT INTO "companies" VALUES('SE','Sea Ltd','NYSE','Singapore',69504745472.0,'USD','Services-Miscellaneous Business Services','Founder-CEO','ADR',1,'yahoo_finance_search','2026-09-01','symbol and company name confirmed (score=100)',100.0,'Forrest Li','Sea Limited operates established network effects across its three core businesses: Garena''s gaming platform benefits from multiplayer network effects, Shopee''s e-commerce marketplace creates two-sided network effects between buyers and sellers with switching costs, and SeaMoney''s digital payments grows more valuable as merchant and user adoption increases.','20-F:https://www.sec.gov/Archives/edgar/data/1703399/000114036126015366/ef20067274_20f.htm','2026-04-17',0,'2026-08-14T19:23:00.918017+00:00','Established',43.814674,22.080614,77.05,199.3,1.51,NULL,'2026-09-01','yahoo_finance_quotesummary','2017-10-20',1.62600002288818359e+01,113.48,2575.2099609375,7686.14,'2026-09-01','yahoo_finance_chart','12eece8488170c2b29425b3121e67c060194a6f1',NULL);
INSERT INTO "companies" VALUES('PDD','PDD Holdings Inc.','Nasdaq','China',119565303808.0,'USD','Services-Business Services, NEC','Founder-departed','ADR',1,'yahoo_finance_search','2026-09-01','symbol and company name confirmed (score=100)',100.0,'Colin Huang','PDD Holdings (operating Pinduoduo and Temu) has an established network effect as a two-sided marketplace where more buyers attract more sellers and vice versa, with its social shopping and group-buying features creating additional viral growth loops that have scaled globally over multiple years.','20-F:https://www.sec.gov/Archives/edgar/data/1737806/000110465926050727/pdd-20251231x20f.htm','2026-04-29',0,'2026-08-14T19:23:08.044945+00:00','Established',9.081081,6.787252,71.94,139.41,-0.005,NULL,'2026-09-01','yahoo_finance_quotesummary','2018-07-26',2.67000007629394531e+01,84.0,2837.43994140625,7686.14,'2026-09-01','yahoo_finance_chart','1449c25ef546ac11c2c11357a3dee29e6e7a0f0d',NULL);
INSERT INTO "companies" VALUES('CPNG','Coupang, Inc.','NYSE','South Korea',28828729344.0,'USD','Retail-Catalog & Mail-Order Houses','Founder-CEO','ADR',1,'yahoo_finance_search','2026-09-01','symbol and company name confirmed (score=100)',100.0,'Bom Kim','Coupang operates an established two-sided marketplace connecting consumers with sellers and service providers, with significant scale in South Korea creating switching costs through delivery infrastructure, product selection, and buyer-seller liquidity that has compounded over multiple years.','DEF 14A:https://www.sec.gov/Archives/edgar/data/1834584/000114036126017102/ny20063059x1_def14a.htm','2026-04-27',0,'2026-08-14T19:23:13.786576+00:00','Established',NULL,59.673763,14.92,34.075,1.157,NULL,'2026-09-01','yahoo_finance_quotesummary','2021-03-11',49.25,16.06,3.939340087890625e+03,7686.14,'2026-09-01','yahoo_finance_chart','dcba409f8c6822d20edc6a9a2704fabfaf0bab6d',NULL);
INSERT INTO "companies" VALUES('GRAB','Grab Holdings Ltd','Nasdaq','Singapore',14483208192.0,'USD','Services-Business Services, NEC','Founder-CEO','ADR',1,'yahoo_finance_search','2026-09-01','symbol and company name confirmed (score=100)',100.0,'Anthony Tan','Grab operates an established network effect as a multi-sided platform connecting drivers, merchants, and consumers across ride-hailing and delivery services, where increased supply attracts more demand and vice versa, creating compounding value and switching costs that have scaled across Southeast Asia since 2012.','20-F:https://www.sec.gov/Archives/edgar/data/1855612/000185561226000020/ck0001855612-20251231.htm','2026-03-06',0,'2026-08-14T19:23:21.567351+00:00','Established',32.18182,25.467627,3.18,6.62,0.89,NULL,'2026-09-01','yahoo_finance_quotesummary','2020-12-01',1.18900003433227539e+01,3.54,3.662449951171875e+03,7686.14,'2026-09-01','yahoo_finance_chart','6f97d99f57433a67feac22f87e78a8aa71b3118c',NULL);
INSERT INTO "companies" VALUES('ZAL.DE','ZALANDO SE','XETRA','Germany',6007877120.0,'EUR',NULL,'Founder-CEO','primary',1,'yahoo_finance_search','2026-08-31','symbol and company name confirmed (score=100) — resolved to ''ZAL.DE''',8.23529411764705798e+01,'Robert Gentz','Zalando operates an established two-sided marketplace connecting fashion brands and consumers across Europe, with network effects evident through its B2B operating system that enables third-party sellers and its position as a go-to destination that benefits from both supply-side scale (more brands attract more shoppers) and demand-side scale (more shoppers attract more brands).','DE:https://corporate.zalando.com/en/investor-relations/our-management-board','2026-08-31',0,'2026-08-19T21:22:01.757656+00:00','Established',68.33333,13.301899,18.61,30.43,1.586,NULL,'2026-08-31','yahoo_finance_quotesummary','2014-10-01',21.5,24.6,1.9461600341796875e+03,7711.76,'2026-08-31','yahoo_finance_chart','7363cd2cee88b69ef425b3c3832c0d8b580bd510',NULL);
INSERT INTO "companies" VALUES('035420.KS','NAVER CORP','KOSPI','South Korea',NULL,NULL,NULL,'N/A','primary',1,'yahoo_finance_search','2026-09-01','symbol and company name confirmed (score=100) — resolved to ''035420.KS''',100.0,'Lee Hae-jin',NULL,NULL,NULL,0,'2026-08-25T14:11:52.777235+00:00',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO "companies" VALUES('0700.HK','Tencent Holdings','HKEX','Hong Kong',3977865854976.0,'HKD',NULL,'Founder-CEO','primary',1,'yahoo_finance_search','2026-09-01','symbol and company name confirmed (score=100)',100.0,'Ma Huateng (Pony Ma)','Tencent operates an established network effect through WeChat''s massive social network and payment ecosystem, Tencent Games'' multiplayer platforms, and its cloud/marketing services that benefit from scale, all of which have demonstrated compounding user growth and strong switching costs over multiple years as core to its business model.','HK:https://www.tencent.com/en-us/investors/board-members.html','2026-09-01',0,'2026-08-26T22:26:25.300864+00:00','Established',14.871967,12.214288,411.0,683.0,0.745,1.17,'2026-09-01','yahoo_finance_quotesummary','2004-06-16',7.65139997005462646e-01,441.4,1133.56005859375,7686.14,'2026-09-01','yahoo_finance_chart','80b2b9a6d19da73da3bcff8e40ecab138c235214',NULL);
INSERT INTO "companies" VALUES('ADYEN.AS','Adyen','Euronext Amsterdam','Netherlands',32450543616.0,'EUR',NULL,'Founder-CEO','primary',1,'yahoo_finance_search','2026-09-01','symbol and company name confirmed (score=100)',100.0,'Pieter van der Does','Adyen operates a two-sided payments platform connecting merchants and payment methods, creating network effects as more merchants attract more payment providers and vice versa, though the network effect is secondary to its core infrastructure and processing capabilities.','NL:https://investors.adyen.com/governance','2026-09-01',0,'2026-08-27T03:39:42.448594+00:00','Emerging',28.868296,21.990932,772.4,1600.8,1.86,NULL,'2026-09-01','yahoo_finance_quotesummary','2018-06-13',455.0,1028.0,2775.6298828125,7686.14,'2026-09-01','yahoo_finance_chart','5ad0069802560d5f65a614c2a2565a35e523a1c2',NULL);
INSERT INTO "companies" VALUES('ZAL.F','ZALANDO SE','XETRA','Germany',5937052160.0,'EUR',NULL,'Founder-CEO','primary',1,'yahoo_finance_search','2026-09-01','symbol and company name confirmed (score=100) — resolved to ''ZAL.F''',8.23529411764705798e+01,'Robert Gentz','Zalando operates an established two-sided marketplace connecting fashion brands and consumers across Europe, with network effects evident in its B2B operating system for e-commerce and its position as a go-to destination that strengthens as more brands and customers participate.','DE:https://corporate.zalando.com/en/investor-relations/our-management-board','2026-09-01',0,'2026-09-01T13:14:59.716762+00:00','Established',67.52777,13.145088,18.64,30.16,1.586,NULL,'2026-09-01','yahoo_finance_quotesummary','2014-10-01',2.1569000244140625e+01,24.31,1.9461600341796875e+03,7686.14,'2026-09-01','yahoo_finance_chart','7363cd2cee88b69ef425b3c3832c0d8b580bd510',NULL);
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
, first_seen_at TEXT, summary_input_fingerprint TEXT);
INSERT INTO "designations" VALUES('e63ae8afca8ffeba','ESAIY','FDA','Breakthrough Therapy','2019-06-17','Lecanemab (Leqembi)','Early Alzheimer''s disease','NCT03887455','manual_seed:fda_breakthrough_seed.csv','2026-08-10','Eisai','Lecanemab is a treatment for early Alzheimer''s disease that received Breakthrough Therapy designation, meaning the FDA determined it shows substantial improvement over existing therapies for a serious condition based on preliminary clinical evidence. This designation matters clinically because it indicates the drug demonstrated meaningful effects on slowing cognitive decline in early-stage patients, a population with very limited treatment options that can modify disease progression. Lecanemab is one of the first therapies to demonstrate actual slowing of Alzheimer''s disease progression rather than just temporarily masking symptoms, representing a fundamentally different approach from older medications like donepezil that only provide symptomatic relief without affecting underlying disease.','High signal','2026-08-29T14:20:38.023192+00:00',NULL,NULL,'6e22ace07287648e29c0680f2e73ec251cb917fa');
INSERT INTO "designations" VALUES('cc178b137b0e1a6e','VRTX','FDA','Breakthrough Therapy','2021-01-28','Exagamglogene autotemcel (Casgevy)','Severe sickle cell disease','NCT03745287','manual_seed:fda_breakthrough_seed.csv','2026-08-10','Vertex Pharmaceuticals','Exagamglogene autotemcel (Casgevy) is a gene therapy designed to treat severe sickle cell disease by modifying a patient''s own blood stem cells to produce healthy hemoglobin and reduce painful vaso-occlusive crises. The Breakthrough Therapy designation indicates the FDA recognized early clinical evidence that this treatment addresses a serious unmet need in patients with severe disease who have limited curative options beyond risky bone marrow transplants. This represents a potentially curative one-time gene therapy approach using the patient''s own edited cells, contrasting with existing chronic management strategies like hydroxyurea or recently approved therapies that require repeated infusions or ongoing medication.','High signal','2026-08-29T14:20:43.359699+00:00',NULL,NULL,'29436fcc320eeb27fbd3c421d04e10fce18cbef6');
INSERT INTO "designations" VALUES('c59e44d78ab40bb7','DAWNGBX','FDA','Breakthrough Therapy','2022-08-15','Tovorafenib (Ojemda)','Relapsed or progressive pediatric low-grade glioma','NCT04775485','manual_seed:fda_breakthrough_seed.csv','2026-08-10','Day One Biopharmaceuticals','Tovorafenib is being developed to treat children with low-grade gliomas (slow-growing brain tumors) that have come back or continued to grow despite previous treatment. The Breakthrough Therapy designation means FDA recognized that early evidence suggests this drug may offer a substantial improvement over existing options for these young patients who have limited alternatives after standard therapies fail. Pediatric low-grade glioma has historically relied on chemotherapy and sometimes radiation when tumors progress, but targeted therapies specifically designed for the molecular characteristics of these childhood brain tumors have been limited, making new treatment options particularly valuable for this patient population.','High signal','2026-08-29T22:55:23.533648+00:00',NULL,NULL,'3193cef37e5ca95ad20de999ea1a80598a247db2');
INSERT INTO "designations" VALUES('324d564d8f11bd8f','VRTX','EMA','PRIME','2020-09-22','Exagamglogene autotemcel (Casgevy)','Severe sickle cell disease','NCT03745287','manual_seed:ema_prime_seed.csv','2026-08-11','Vertex Pharmaceuticals','Exagamglogene autotemcel (Casgevy) is a one-time gene therapy designed to treat severe sickle cell disease by modifying a patient''s own blood stem cells to produce functional hemoglobin, potentially eliminating or significantly reducing painful vaso-occlusive crises and other complications. The PRIME designation from European regulators indicates this addresses a major unmet need in a serious condition where current treatments primarily manage symptoms rather than correcting the underlying genetic defect. This represents a potentially curative approach through gene editing, fundamentally different from existing treatments like hydroxyurea, chronic transfusions, and bone marrow transplants, offering the possibility of a functional cure without requiring a matched donor.','High signal','2026-08-29T14:21:00.403340+00:00','https://www.globenewswire.com/news-release/2020/09/22/2097309/0/en/CRISPR-Therapeutics-and-Vertex-Pharmaceuticals-Announce-Priority-Medicines-PRIME-Designation-Granted-by-the-European-Medicines-Agency-EMA-to-CTX001-for-the-Treatment-of-Sickle-Cell.html',NULL,'7bfb7295fcf8f94edb959ae6894e0cd8c6203290');
INSERT INTO "designations" VALUES('390dfc241b225c0a','VRTX','EMA','PRIME','2021-04-26','Exagamglogene autotemcel (Casgevy)','Transfusion-dependent beta thalassemia','NCT03745287','manual_seed:ema_prime_seed.csv','2026-08-11','Vertex Pharmaceuticals','Exagamglogene autotemcel (Casgevy) is a gene therapy designed to treat transfusion-dependent beta thalassemia, a genetic blood disorder where patients require regular blood transfusions to survive due to inadequate hemoglobin production. The PRIME designation from the European Medicines Agency indicates this therapy addresses a critical unmet medical need and has shown sufficient evidence to warrant accelerated regulatory support, suggesting it may reduce or eliminate the need for lifelong transfusions. This represents a potentially curative one-time gene therapy approach compared to the current standard of care requiring chronic lifelong blood transfusions every 2-4 weeks, or in rare cases allogeneic bone marrow transplantation which carries significant risks and requires a matched donor.','High signal','2026-08-29T14:21:06.173560+00:00','https://www.globenewswire.com/news-release/2021/04/26/2216841/0/en/Vertex-and-CRISPR-Therapeutics-Announce-Priority-Medicines-PRIME-Designation-Granted-by-the-European-Medicines-Agency-to-CTX001-for-Transfusion-Dependent-Beta-Thalassemia.html',NULL,'b80a1fea4adfb4226fa8d4abaae26e5133c7bb90');
INSERT INTO "designations" VALUES('32bcd2fd3fa02d80','ATRA','EMA','PRIME','2016-10-01','Tabelecleucel (Ebvallo)','Epstein-Barr virus-positive post-transplant lymphoproliferative disease (EBV+ PTLD)','NCT03394365','manual_seed:ema_prime_seed.csv','2026-08-11','Atara Biotherapeutics','Tabelecleucel is a cell therapy designed to treat a rare and aggressive cancer called EBV-positive post-transplant lymphoproliferative disease, which occurs when transplant patients develop uncontrolled growth of Epstein-Barr virus-infected cells. The PRIME designation from the European Medicines Agency signals that regulators recognize this addresses a significant unmet medical need where current treatment options are limited or inadequate. This represents a targeted cellular immunotherapy approach for a condition that currently lacks approved therapies and typically relies on reducing immune suppression (risking transplant rejection) or chemotherapy with limited effectiveness in this vulnerable patient population.','High signal','2026-08-29T14:21:11.799916+00:00','https://www.sec.gov/Archives/edgar/data/1604464/000119312517382414/d489039dex991.htm',NULL,'79a70a45f457f57a39e0011e46d4b93ecb1ee0f2');
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
INSERT INTO "ownership" VALUES(27,'MELI','Marcos Galperin','Executive Chairman of the Board',7.0,'DEF 14A:https://www.sec.gov/Archives/edgar/data/1099590/000109959026000010/meli-20260423.htm','2026-04-23');
INSERT INTO "ownership" VALUES(28,'SE','Forrest Li','Founder and Chief Executive Officer, Chairman of Sea Limited',16.0,'20-F:https://www.sec.gov/Archives/edgar/data/1703399/000114036126015366/ef20067274_20f.htm','2026-04-17');
INSERT INTO "ownership" VALUES(29,'PDD','Colin Huang','no active leadership role',24.8,'20-F:https://www.sec.gov/Archives/edgar/data/1737806/000110465926050727/pdd-20251231x20f.htm','2026-04-29');
INSERT INTO "ownership" VALUES(30,'CPNG','Bom Kim','Chief Executive Officer and Chairman of the Board',74.3,'DEF 14A:https://www.sec.gov/Archives/edgar/data/1834584/000114036126017102/ny20063059x1_def14a.htm','2026-04-27');
INSERT INTO "ownership" VALUES(31,'GRAB','Anthony Tan','Founder, Chairman and Chief Executive Officer',3.2,'20-F:https://www.sec.gov/Archives/edgar/data/1855612/000185561226000020/ck0001855612-20251231.htm','2026-03-06');
INSERT INTO "ownership" VALUES(32,'ZAL.DE','Robert Gentz','Co-founder and co-CEO',NULL,'DE:https://corporate.zalando.com/en/investor-relations/our-management-board','2026-08-25');
INSERT INTO "ownership" VALUES(33,'035420.KS','Lee Hae-jin','Chairman of the Board (이사회 의장)',NULL,'KR:DART exctvSttus corp_code=00266961','2026-08-25');
INSERT INTO "ownership" VALUES(34,'MELI','Marcos Galperin','Executive Chairman of the Board',7.0,'DEF 14A:https://www.sec.gov/Archives/edgar/data/1099590/000109959026000010/meli-20260423.htm','2026-04-23');
INSERT INTO "ownership" VALUES(35,'SE','Forrest Li','Founder and Chief Executive Officer, Chairman of Sea Limited',16.0,'20-F:https://www.sec.gov/Archives/edgar/data/1703399/000114036126015366/ef20067274_20f.htm','2026-04-17');
INSERT INTO "ownership" VALUES(36,'PDD','Colin Huang','no active leadership role',24.8,'20-F:https://www.sec.gov/Archives/edgar/data/1737806/000110465926050727/pdd-20251231x20f.htm','2026-04-29');
INSERT INTO "ownership" VALUES(37,'CPNG','Bom Kim','Chief Executive Officer and Chairman of the Board',74.3,'DEF 14A:https://www.sec.gov/Archives/edgar/data/1834584/000114036126017102/ny20063059x1_def14a.htm','2026-04-27');
INSERT INTO "ownership" VALUES(38,'GRAB','Anthony Tan','Founder, Chairman and Chief Executive Officer',3.2,'20-F:https://www.sec.gov/Archives/edgar/data/1855612/000185561226000020/ck0001855612-20251231.htm','2026-03-06');
INSERT INTO "ownership" VALUES(39,'ZAL.DE','Robert Gentz','Co-CEO',NULL,'DE:https://corporate.zalando.com/en/investor-relations/our-management-board','2026-08-26');
INSERT INTO "ownership" VALUES(40,'035420.KS','Lee Hae-jin','Chair of the Board (이사회 의장)',NULL,'KR:DART exctvSttus corp_code=00266961','2026-08-26');
INSERT INTO "ownership" VALUES(41,'0700.HK','Ma Huateng (Pony Ma)','Chairman and Chief Executive Officer',NULL,'HK:https://www.tencent.com/en-us/investors/board-members.html','2026-08-26');
INSERT INTO "ownership" VALUES(42,'MELI','Marcos Galperin','Executive Chairman of the Board',7.0,'DEF 14A:https://www.sec.gov/Archives/edgar/data/1099590/000109959026000010/meli-20260423.htm','2026-04-23');
INSERT INTO "ownership" VALUES(43,'SE','Forrest Li','Founder and Chief Executive Officer; Chairman of Sea Limited',16.0,'20-F:https://www.sec.gov/Archives/edgar/data/1703399/000114036126015366/ef20067274_20f.htm','2026-04-17');
INSERT INTO "ownership" VALUES(44,'PDD','Colin Huang','No active leadership role',24.8,'20-F:https://www.sec.gov/Archives/edgar/data/1737806/000110465926050727/pdd-20251231x20f.htm','2026-04-29');
INSERT INTO "ownership" VALUES(45,'CPNG','Bom Kim','Chief Executive Officer and Chairman of the Board',74.3,'DEF 14A:https://www.sec.gov/Archives/edgar/data/1834584/000114036126017102/ny20063059x1_def14a.htm','2026-04-27');
INSERT INTO "ownership" VALUES(46,'GRAB','Anthony Tan','Founder, Chairman and Chief Executive Officer',3.2,'20-F:https://www.sec.gov/Archives/edgar/data/1855612/000185561226000020/ck0001855612-20251231.htm','2026-03-06');
INSERT INTO "ownership" VALUES(47,'ZAL.DE','Robert Gentz','Co-founder and co-CEO',NULL,'DE:https://corporate.zalando.com/en/investor-relations/our-management-board','2026-08-26');
INSERT INTO "ownership" VALUES(48,'035420.KS','Lee Hae-jin','Chairman of the Board (이사회 의장)',NULL,'KR:DART exctvSttus corp_code=00266961','2026-08-26');
INSERT INTO "ownership" VALUES(49,'0700.HK','Ma Huateng (Pony Ma)','Ma Huateng (Pony Ma) is Chairman of the Board and Chief Executive Officer',NULL,'HK:https://www.tencent.com/en-us/investors/board-members.html','2026-08-26');
INSERT INTO "ownership" VALUES(50,'ADYEN.AS','Pieter van der Does','Co-Chief Executive Officer',2.98,'NL:https://investors.adyen.com/governance','2026-08-26');
INSERT INTO "ownership" VALUES(51,'MELI','Marcos Galperin','Executive Chairman of the Board',7.0,'DEF 14A:https://www.sec.gov/Archives/edgar/data/1099590/000109959026000010/meli-20260423.htm','2026-04-23');
INSERT INTO "ownership" VALUES(52,'SE','Forrest Li','Founder and Chief Executive Officer, Chairman of Sea Limited',16.0,'20-F:https://www.sec.gov/Archives/edgar/data/1703399/000114036126015366/ef20067274_20f.htm','2026-04-17');
INSERT INTO "ownership" VALUES(53,'PDD','Colin Huang','No active leadership role',24.8,'20-F:https://www.sec.gov/Archives/edgar/data/1737806/000110465926050727/pdd-20251231x20f.htm','2026-04-29');
INSERT INTO "ownership" VALUES(54,'CPNG','Bom Kim','Chief Executive Officer and Chairman of the Board',74.3,'DEF 14A:https://www.sec.gov/Archives/edgar/data/1834584/000114036126017102/ny20063059x1_def14a.htm','2026-04-27');
INSERT INTO "ownership" VALUES(55,'GRAB','Anthony Tan','Founder, Chairman and Chief Executive Officer',3.2,'20-F:https://www.sec.gov/Archives/edgar/data/1855612/000185561226000020/ck0001855612-20251231.htm','2026-03-06');
INSERT INTO "ownership" VALUES(56,'ZAL.DE','Robert Gentz','Co-founder and co-CEO',NULL,'DE:https://corporate.zalando.com/en/investor-relations/our-management-board','2026-08-28');
INSERT INTO "ownership" VALUES(57,'035420.KS','Lee Hae-jin','Chairman of the Board (이사회 의장)',NULL,'KR:DART exctvSttus corp_code=00266961','2026-08-28');
INSERT INTO "ownership" VALUES(58,'0700.HK','Ma Huateng (Pony Ma)','Chairman and Chief Executive Officer',NULL,'HK:https://www.tencent.com/en-us/investors/board-members.html','2026-08-28');
INSERT INTO "ownership" VALUES(59,'ADYEN.AS','Pieter van der Does','Co-Chief Executive Officer',2.98,'NL:https://investors.adyen.com/governance','2026-08-28');
INSERT INTO "ownership" VALUES(60,'MELI','Marcos Galperin','Executive Chairman of the Board',7.0,'DEF 14A:https://www.sec.gov/Archives/edgar/data/1099590/000109959026000010/meli-20260423.htm','2026-04-23');
INSERT INTO "ownership" VALUES(61,'SE','Forrest Li','Founder and Chief Executive Officer, Chairman of Sea Limited',16.0,'20-F:https://www.sec.gov/Archives/edgar/data/1703399/000114036126015366/ef20067274_20f.htm','2026-04-17');
INSERT INTO "ownership" VALUES(62,'PDD','Colin Huang','no active leadership role',24.8,'20-F:https://www.sec.gov/Archives/edgar/data/1737806/000110465926050727/pdd-20251231x20f.htm','2026-04-29');
INSERT INTO "ownership" VALUES(63,'CPNG','Bom Kim','Founder, Chief Executive Officer and Chairman of the Board',74.3,'DEF 14A:https://www.sec.gov/Archives/edgar/data/1834584/000114036126017102/ny20063059x1_def14a.htm','2026-04-27');
INSERT INTO "ownership" VALUES(64,'GRAB','Anthony Tan','Founder, Chairman and Chief Executive Officer',3.2,'20-F:https://www.sec.gov/Archives/edgar/data/1855612/000185561226000020/ck0001855612-20251231.htm','2026-03-06');
INSERT INTO "ownership" VALUES(65,'ZAL.DE','Robert Gentz','Co-founder and co-CEO',NULL,'DE:https://corporate.zalando.com/en/investor-relations/our-management-board','2026-08-28');
INSERT INTO "ownership" VALUES(66,'035420.KS','Lee Hae-jin','Chairman of the Board (이사회 의장)',NULL,'KR:DART exctvSttus corp_code=00266961','2026-08-28');
INSERT INTO "ownership" VALUES(67,'0700.HK','Ma Huateng (Pony Ma)','Chairman and Chief Executive Officer',NULL,'HK:https://www.tencent.com/en-us/investors/board-members.html','2026-08-28');
INSERT INTO "ownership" VALUES(68,'ADYEN.AS','Pieter van der Does','Co-Chief Executive Officer',2.98,'NL:https://investors.adyen.com/governance','2026-08-28');
INSERT INTO "ownership" VALUES(69,'MELI','Marcos Galperin','Executive Chairman of the Board',7.0,'DEF 14A:https://www.sec.gov/Archives/edgar/data/1099590/000109959026000010/meli-20260423.htm','2026-04-23');
INSERT INTO "ownership" VALUES(70,'SE','Forrest Li','Founder and Chief Executive Officer; Chairman of Sea Limited',16.0,'20-F:https://www.sec.gov/Archives/edgar/data/1703399/000114036126015366/ef20067274_20f.htm','2026-04-17');
INSERT INTO "ownership" VALUES(71,'PDD','Colin Huang','No active leadership role; Zheng Huang is listed only as a principal shareholder, not among directors and executive officers',24.8,'20-F:https://www.sec.gov/Archives/edgar/data/1737806/000110465926050727/pdd-20251231x20f.htm','2026-04-29');
INSERT INTO "ownership" VALUES(72,'CPNG','Bom Kim','Chief Executive Officer and Chairman of the Board',74.3,'DEF 14A:https://www.sec.gov/Archives/edgar/data/1834584/000114036126017102/ny20063059x1_def14a.htm','2026-04-27');
INSERT INTO "ownership" VALUES(73,'GRAB','Anthony Tan','Founder, Chairman and Chief Executive Officer',3.2,'20-F:https://www.sec.gov/Archives/edgar/data/1855612/000185561226000020/ck0001855612-20251231.htm','2026-03-06');
INSERT INTO "ownership" VALUES(74,'ZAL.DE','Robert Gentz','Robert Gentz is Co-founder and co-CEO',NULL,'DE:https://corporate.zalando.com/en/investor-relations/our-management-board','2026-08-29');
INSERT INTO "ownership" VALUES(75,'035420.KS','Lee Hae-jin','Chairman of the Board (이사회 의장)',NULL,'KR:DART exctvSttus corp_code=00266961','2026-08-29');
INSERT INTO "ownership" VALUES(76,'0700.HK','Ma Huateng (Pony Ma)','Chairman and Chief Executive Officer',NULL,'HK:https://www.tencent.com/en-us/investors/board-members.html','2026-08-29');
INSERT INTO "ownership" VALUES(77,'ADYEN.AS','Pieter van der Does','Co-Chief Executive Officer',2.98,'NL:https://investors.adyen.com/governance','2026-08-29');
INSERT INTO "ownership" VALUES(79,'0700.HK','Ma Huateng (Pony Ma)','Chairman and Chief Executive Officer',NULL,'HK:https://www.tencent.com/en-us/investors/board-members.html','2026-08-29');
INSERT INTO "ownership" VALUES(80,'ZAL.F','Robert Gentz','Co-founder and co-CEO',NULL,'DE:https://corporate.zalando.com/en/investor-relations/our-management-board','2026-09-01');
CREATE TABLE site_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_generated_at TEXT
);
INSERT INTO "site_state" VALUES(1,'2026-09-01T13:15:26.767768+00:00');
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
INSERT INTO "tracked_outcomes" VALUES(12,'0700.HK','founder_stock','0700.HK','2026-08-26','High signal','yahoo_finance_chart',445.4,'2026-08-26','2026-11-26',NULL,NULL,'2027-02-26',NULL,NULL,'2027-08-26',NULL,NULL,NULL);
INSERT INTO "tracked_outcomes" VALUES(13,'ADYEN.AS','founder_stock','ADYEN.AS','2026-08-26','Moderate signal','yahoo_finance_chart',1071.4,'2026-08-26','2026-11-26',NULL,NULL,'2027-02-26',NULL,NULL,'2027-08-26',NULL,NULL,NULL);
INSERT INTO "tracked_outcomes" VALUES(14,'ZAL.F','founder_stock','ZAL.F','2026-09-01','High signal','yahoo_finance_chart',24.31,'2026-09-01','2026-12-01',NULL,NULL,'2027-03-01',NULL,NULL,'2027-09-01',NULL,NULL,NULL);
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
INSERT INTO "trials" VALUES('NCT03887455','ClinicalTrials.gov','PHASE3','ACTIVE_NOT_RECRUITING','2019-03-27','2029-06-30','Early Alzheimer''s Disease','2026-09-01T13:14:38.484491+00:00');
INSERT INTO "trials" VALUES('NCT03745287','ClinicalTrials.gov','PHASE2, PHASE3','COMPLETED','2018-11-27','2025-07-07','Sickle Cell Disease; Hematological Diseases; Hemoglobinopathies','2026-09-01T13:14:45.127773+00:00');
INSERT INTO "trials" VALUES('NCT04775485','ClinicalTrials.gov','PHASE2','RECRUITING','2021-04-22','2027-05-31','Low-grade Glioma; Advanced Solid Tumor','2026-09-01T13:14:44.671540+00:00');
INSERT INTO "trials" VALUES('NCT03394365','ClinicalTrials.gov','PHASE3','RECRUITING','2017-12-29','2030-05-31','Epstein-Barr Virus+ Associated Post-transplant Lymphoproliferative Disease (EBV+ PTLD); Solid Organ Transplant Complications; Lymphoproliferative Disorders; Allogeneic Hematopoietic Cell Transplant; Stem Cell Transplant Complications','2026-09-01T13:14:45.506099+00:00');
CREATE TABLE user_notes (
    note_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id TEXT NOT NULL,
    date_written TEXT NOT NULL,
    note_text TEXT NOT NULL
);
INSERT INTO "user_notes" VALUES(1,'cc178b137b0e1a6e','2026-08-14','First real CRISPR therapy approval - worth tracking how the pricing/reimbursement story plays out.');
INSERT INTO "user_notes" VALUES(3,'ZAL.DE','2026-08-19','ownership_pct unavailable for both Zalando co-founders (Robert Gentz, David Schneider): the only source disclosing their combined stake (~5%) is a PNG chart on corporate.zalando.com/en/investor-relations/shareholder-structure, not machine-readable text this pipeline can extract. BaFin''s WpHG voting-rights database has nothing on file for either individually (both below the 3% mandatory disclosure threshold). CONSEQUENCE: if either founder''s leadership status changes (e.g. steps back from CEO to Chairman), the automated Founder-Chair vs. Founder-departed classification cannot verify the required >5% ownership threshold from any scraped source. Check the shareholder-structure page manually before trusting that classification.');
CREATE TABLE watchlist (
    entry_id TEXT PRIMARY KEY,
    added_at TEXT NOT NULL
, entry_kind TEXT NOT NULL DEFAULT 'pipeline', company_name TEXT, verification_source TEXT, verification_date TEXT, verification_reason TEXT);
DELETE FROM "sqlite_sequence";
INSERT INTO "sqlite_sequence" VALUES('user_notes',3);
INSERT INTO "sqlite_sequence" VALUES('ownership',80);
INSERT INTO "sqlite_sequence" VALUES('tracked_outcomes',14);
COMMIT;
