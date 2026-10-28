"""Build the final Big Data Analytics mini-project report.

Reuses the original NLP report as a template (front-matter layout, fonts,
margins, page breaks) and replaces all project content with the CustomerIQ
Customer Segmentation & Purchase Analytics platform, including real pipeline
outputs and generated charts.

Output: BDA_MiniProject_Report_Kinjal_Ashish.docx
"""

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.shared import Inches, Pt, RGBColor

BASE = Path(__file__).resolve().parents[1]
SRC = BASE / "NLP_MiniProject_Report_Kinjal_Ashish.docx"
DST = BASE / "BDA_MiniProject_Report_Kinjal_Ashish.docx"
ASSETS = BASE / "report_assets"

CODE_FONT = "Consolas"
CODE_SIZE = Pt(9)
CODE_COLOR = RGBColor(0x1A, 0x1A, 0x1A)

doc = Document(str(SRC))


# ---------------------------------------------------------------------------
# front matter edits (in place, preserving template formatting)
# ---------------------------------------------------------------------------

def set_para_text(p, text: str) -> None:
    """Replace paragraph text, keeping the first run's formatting."""
    if not p.runs:
        p.add_run(text)
        return
    p.runs[0].text = text
    for r in p.runs[1:]:
        r._element.getparent().remove(r._element)


paras = doc.paragraphs
set_para_text(paras[3], "Big Data Analytics Mini Project Report")
set_para_text(paras[5], "CustomerIQ - Customer Segmentation & Purchase Analytics Platform")
set_para_text(paras[8], "Big Data Analytics Mini Project Semester VII in degree of")
# authors: two lines inside the centred BY-block paragraph
set_para_text(paras[13], "Ashish Anil Sharma (Roll No. 54)\nKinjal Shivprasad Ojha (Roll No. 21)")
set_para_text(paras[24], "Big Data Analytics Mini Project Report Approval")
set_para_text(
    paras[26],
    'This project report entitled "CustomerIQ - Customer Segmentation & Purchase '
    'Analytics Platform" by Mr. Ashish Anil Sharma (Roll No. 54) and Mr. '
    "Kinjal Shivprasad Ojha (Roll No. 21) is approved for the Mini Project "
    "Semester VII project work of B.E. CMPN at Shree L. R. Tiwari College of "
    "Engineering, in the academic year 2026-2027.",
)


# ---------------------------------------------------------------------------
# delete old body (from the bold 1. Introduction heading to the end)
# ---------------------------------------------------------------------------

intro_idx = None
for i, p in enumerate(doc.paragraphs):
    if p.text.strip() == "1. Introduction" and any(r.bold for r in p.runs):
        intro_idx = i
        break
if intro_idx is None:
    raise RuntimeError("Could not locate the Introduction heading")

for p in doc.paragraphs[intro_idx:]:
    p._element.getparent().remove(p._element)


# ---------------------------------------------------------------------------
# body builders
# ---------------------------------------------------------------------------

def heading(text: str):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(14)
    return p


def subheading(text: str):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(text)
    r.bold = True
    return p


def body(text: str):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    p.add_run(text)
    return p


def code(text: str, console: bool = False):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(0)
    r = p.add_run(text)
    r.font.name = CODE_FONT
    r.font.size = CODE_SIZE
    if not console:
        r.font.color.rgb = CODE_COLOR
    return p


def code_block(lines: list[str], console: bool = False):
    for line in lines:
        code(line if line else " ", console=console)


def picture(path: Path, width_in: float):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(6)
    p.add_run().add_picture(str(path), width=Inches(width_in))
    return p


def page_break():
    p = doc.add_paragraph()
    p.add_run().add_break(WD_BREAK.PAGE)
    return p


# ===========================================================================
# 1. INTRODUCTION
# ===========================================================================
page_break()
heading("1. Introduction")
body(
    "In today's retail and e-commerce industry, businesses accumulate large volumes of "
    "transaction data, yet converting that data into actionable customer insight remains "
    "difficult. Marketing and retention budgets are most effective when they are aimed at "
    "the right customers, but identifying who those customers are requires analysing "
    "purchase behaviour across thousands of transactions. Traditional spreadsheet tools "
    "cannot scale to this task, and manual segmentation is slow, subjective, and hard to "
    "reproduce.\n"
    "\n"
    "This project, titled \"CustomerIQ - Customer Segmentation & Purchase Analytics "
    "Platform\", addresses this problem with RFM (Recency, Frequency, Monetary) analysis "
    "combined with unsupervised machine learning. RFM analysis scores every customer on "
    "three dimensions: how recently they purchased (Recency), how often they purchase "
    "(Frequency), and how much they spend (Monetary). Customers are then grouped into "
    "behavioural segments using the K-Means clustering algorithm from Apache Spark's "
    "MLlib, which allows the computation to run in a distributed fashion over large "
    "transaction datasets.\n"
    "\n"
    "The deliverable is a complete analytics platform rather than a standalone script. "
    "Retail transaction CSV files are uploaded through a web interface, validated against "
    "a configurable schema, processed by a PySpark data engine, and stored in PostgreSQL "
    "and Parquet. A FastAPI backend exposes the results through versioned REST endpoints, "
    "and a React dashboard presents business users with KPI summaries, revenue trends, "
    "segment distributions, and a searchable customer explorer.\n"
    "\n"
    "The main objectives of this project are:\n"
    "1. To ingest retail transaction CSV files with configurable column mapping and "
    "transparent data-quality validation.\n"
    "2. To compute per-customer RFM metrics at scale using PySpark DataFrames and "
    "Spark SQL aggregations.\n"
    "3. To apply documented handling of skewed features, scale them with Spark MLlib, "
    "and segment customers using K-Means clustering.\n"
    "4. To evaluate clustering quality with the silhouette score and select the number "
    "of clusters deterministically using a fixed random seed.\n"
    "5. To map arbitrary cluster identifiers to interpretable business segments such as "
    "Champions, Loyal Customers, and At Risk customers.\n"
    "6. To persist results in PostgreSQL with Parquet analytical artifacts, serve them "
    "through a REST API, and visualise them in a professional analytics dashboard."
)

# ===========================================================================
# 2. SYSTEM ARCHITECTURE
# ===========================================================================
heading("2. System Architecture")
body(
    "The system follows a layered architecture that separates the presentation tier, "
    "the application tier, and the distributed data-processing tier:\n"
    "\n"
    "1. Presentation Layer: A React application built with Vite and TypeScript provides "
    "the user interface. Tailwind CSS and shadcn/ui supply a restrained design system, "
    "Recharts renders the analytics charts, and TanStack Query manages server state and "
    "job-status polling.\n"
    "\n"
    "2. Application Layer: A FastAPI backend exposes versioned REST endpoints under "
    "/api/v1 for dashboards, customers, segments, datasets, and processing jobs. "
    "Pydantic validates every request and response, and SQLAlchemy provides typed "
    "access to PostgreSQL, where datasets, customers, RFM metrics, segment assignments, "
    "processing jobs, and data-quality reports are stored.\n"
    "\n"
    "3. Data Engine Layer: A PySpark data engine performs the heavy computation. "
    "Transaction records are read from CSV, validated, and transformed into RFM metrics "
    "using Spark SQL aggregations. Frequency and Monetary features are log-transformed "
    "to reduce skew, scaled with StandardScaler, and clustered with the K-Means "
    "implementation from Spark MLlib. Clusters are evaluated with the silhouette score "
    "and mapped to human-readable segment labels.\n"
    "\n"
    "4. Processing and Storage: Long-running Spark work executes in a background job "
    "runner outside the HTTP request cycle, with job state transitions (pending, "
    "running, completed, failed) persisted so history survives restarts. Analytical "
    "outputs are written to Parquet for the data layer and to PostgreSQL for "
    "application-facing queries.\n"
    "\n"
    "The end-to-end pipeline can be summarized as:\n"
    "CSV Upload -> Schema Mapping -> Validation -> Distributed RFM (Spark) -> "
    "Log Transform and Scaling -> K-Means (MLlib) -> Silhouette Evaluation -> "
    "Segment Labeling -> PostgreSQL and Parquet -> REST API -> Dashboard"
)

# ===========================================================================
# 3. IMPLEMENTATION
# ===========================================================================
heading("3. Implementation")
body(
    "The project is organised into separate modules for the frontend, the FastAPI "
    "backend, and the Spark data engine. The repository layout is:\n"
)
code_block([
    "customeriq/",
    "  frontend/            React + Vite + TypeScript dashboard",
    "    src/components/    UI components (shadcn/ui, Tailwind CSS)",
    "    src/pages/         Overview, Customers, Segments, Analytics, Import, Jobs",
    "    src/services/      Typed API client (TanStack Query)",
    "  backend/",
    "    app/api/           Versioned FastAPI routers (/api/v1)",
    "    app/models/        SQLAlchemy models (datasets, customers, jobs, ...)",
    "    app/schemas/       Pydantic request/response schemas",
    "    app/services/      Business logic and repositories",
    "    app/workers/       Background job runner for Spark work",
    "  data_engine/",
    "    ingestion/         CSV reading, schema mapping, validation",
    "    transformations/   RFM computation with Spark SQL",
    "    clustering/        Feature scaling, K-Means, segment labeling",
    "    evaluation/        Silhouette evaluation",
    "    storage/           Parquet and model persistence",
    "  data/raw/            Uploaded CSV datasets",
    "  data/processed/      Parquet analytical datasets",
    "  data/models/         Saved Spark ML models",
    "  docker-compose.yml   PostgreSQL for local development",
])
body(
    "The core of the platform is the data engine. Its central stages are reproduced "
    "below from the actual implementation.\n"
    "\n"
    "Data validation applies a documented exclusion policy: exact duplicates are "
    "collapsed, rows with missing customer identifiers are excluded from "
    "customer-level metrics but counted, unparseable dates and non-positive quantities "
    "or prices are rejected, and cancellation invoices are tracked separately:\n"
)
code_block([
    "# data_engine/ingestion/validate.py (core excerpt)",
    "def validate_transactions(raw: DataFrame):",
    "    report = ValidationReport()",
    "    report.total_rows = raw.count()",
    "    deduped = raw.dropDuplicates(raw.columns)",
    "    report.duplicates_removed = report.total_rows - deduped.count()",
    "    df = (deduped",
    "        .withColumn(\"Quantity\", F.col(\"Quantity\").cast(IntegerType()))",
    "        .withColumn(\"UnitPrice\", F.col(\"UnitPrice\").cast(DoubleType()))",
    "        .withColumn(\"InvoiceDateParsed\",",
    "                    F.try_to_timestamp(F.col(\"InvoiceDate\"), F.lit(DATE_FORMAT)))",
    "        .withColumn(\"IsCancellation\",",
    "                    F.upper(F.col(\"InvoiceNo\")).startswith(F.lit(\"C\"))))",
    "    report.invalid_dates = df.filter(F.col(\"InvoiceDateParsed\").isNull()).count()",
    "    report.cancellation_lines = df.filter(F.col(\"IsCancellation\")).count()",
    "    valid = df.filter(",
    "        F.col(\"InvoiceDateParsed\").isNotNull()",
    "        & F.col(\"CustomerID\").isNotNull() & (F.col(\"CustomerID\") != \"\")",
    "        & (~F.col(\"IsCancellation\"))",
    "        & (F.col(\"Quantity\") > 0) & (F.col(\"UnitPrice\") > 0)",
    "    ).withColumn(\"LineRevenue\", F.round(F.col(\"Quantity\") * F.col(\"UnitPrice\"), 2))",
    "    report.valid_transactions = valid.count()",
    "    return valid, report",
])
body(
    "RFM metrics are computed as distributed aggregations over validated transactions. "
    "The analysis reference date defaults to one day after the latest valid purchase so "
    "runs are reproducible:\n"
)
code_block([
    "# data_engine/transformations/rfm.py (core excerpt)",
    "def compute_rfm(transactions: DataFrame, reference_date=None):",
    "    if reference_date is None:",
    "        reference_date = default_reference_date(transactions)",
    "    return (transactions.groupBy(\"CustomerID\")",
    "        .agg(",
    "            F.datediff(F.lit(reference_date),",
    "                       F.max(\"InvoiceDateParsed\")).alias(\"Recency\"),",
    "            F.countDistinct(\"InvoiceNo\").alias(\"Frequency\"),",
    "            F.round(F.sum(\"LineRevenue\"), 2).alias(\"Monetary\"),",
    "            F.min(\"InvoiceDateParsed\").alias(\"FirstPurchase\"),",
    "            F.max(\"InvoiceDateParsed\").alias(\"LastPurchase\"),",
    "        )",
    "        .withColumn(\"AvgOrderValue\",",
    "                    F.round(F.col(\"Monetary\") / F.col(\"Frequency\"), 2)))",
])
body(
    "Clustering uses Spark MLlib. Frequency and Monetary are strongly right-skewed in "
    "retail data, so both are log-transformed before scaling. The K-Means random seed "
    "is fixed for reproducibility, and the silhouette score is computed for each "
    "candidate cluster count:\n"
)
code_block([
    "# data_engine/clustering/kmeans.py (core excerpt)",
    "def fit_kmeans(rfm: DataFrame, k: int = 6, seed: int = 42):",
    "    featured = (rfm",
    "        .withColumn(\"log_Frequency\", F.log1p(F.col(\"Frequency\")))",
    "        .withColumn(\"log_Monetary\", F.log1p(F.col(\"Monetary\"))))",
    "    assembler = VectorAssembler(",
    "        inputCols=[\"Recency\", \"log_Frequency\", \"log_Monetary\"],",
    "        outputCol=\"features_raw\")",
    "    scaler = StandardScaler(",
    "        inputCol=\"features_raw\", outputCol=\"features\",",
    "        withMean=True, withStd=True)",
    "    assembled = assembler.transform(featured)",
    "    scaled = scaler.fit(assembled).transform(assembled)",
    "    model = KMeans(k=k, seed=seed, featuresCol=\"features\",",
    "                   maxIter=100).fit(scaled)",
    "    preds = model.transform(scaled)",
    "    silhouette = ClusteringEvaluator(",
    "        featuresCol=\"features\", predictionCol=\"prediction\").evaluate(preds)",
    "    return preds, silhouette, model",
])
body(
    "Because cluster identifiers are arbitrary, clusters are ranked by a composite "
    "profile score and mapped onto a fixed label spectrum:\n"
)
code_block([
    "# data_engine/clustering/labeling.py (core excerpt)",
    "SPECTRUM = [\"Champions\", \"Loyal Customers\", \"Potential Loyalists\",",
    "            \"New Customers\", \"At Risk\", \"Hibernating\"]",
    "",
    "def label_clusters(profiles, k):",
    "    # rank clusters by z(Frequency) + z(Monetary) - z(Recency)",
    "    ranked = sorted(profiles,",
    "                    key=lambda p: z_freq[p] + z_mon[p] - z_rec[p],",
    "                    reverse=True)",
    "    # pick labels at evenly spaced positions of the spectrum for k clusters",
    "    positions = [round(i * (len(SPECTRUM) - 1) / (k - 1)) for i in range(k)]",
    "    return {p[\"cluster\"]: SPECTRUM[pos]",
    "            for p, pos in zip(ranked, positions)}",
])
body(
    "The FastAPI layer serves the persisted results with pagination and filtering; "
    "a representative endpoint is:\n"
)
code_block([
    "# backend/app/api/customers.py (representative endpoint)",
    "@app.get(\"/api/v1/customers\", response_model=Page[CustomerOut])",
    "def list_customers(",
    "    segment: str | None = None,",
    "    search: str | None = None,",
    "    sort_by: SortKey = \"monetary\",",
    "    page: int = Query(1, ge=1),",
    "    page_size: int = Query(25, ge=1, le=100),",
    "    db: Session = Depends(get_db),",
    "):",
    "    return customer_repo.list_customers(",
    "        db, segment=segment, search=search, sort_by=sort_by,",
    "        offset=(page - 1) * page_size, limit=page_size,",
    "    )",
])

# ===========================================================================
# 4. TECHNOLOGIES USED
# ===========================================================================
heading("4. Technologies Used")
tech = [
    ("Python 3.14: ",
     "Primary language for the backend services and the PySpark data-engine pipeline."),
    ("Apache Spark 4.2 (PySpark): ",
     "Distributed data processing. Spark SQL aggregations compute RFM metrics; Spark "
     "MLlib provides VectorAssembler, StandardScaler, K-Means, and the silhouette "
     "evaluator used for segmentation."),
    ("FastAPI and Pydantic: ",
     "Versioned REST API with automatic OpenAPI documentation and strict request and "
     "response validation."),
    ("SQLAlchemy and PostgreSQL: ",
     "Relational storage for datasets, customers, RFM metrics, segment assignments, "
     "processing jobs, and data-quality reports."),
    ("React, TypeScript and Vite: ",
     "Frontend single-page application with typed components and fast development "
     "builds."),
    ("Tailwind CSS and shadcn/ui: ",
     "Restrained enterprise design system used across all dashboard screens."),
    ("Recharts: ",
     "Chart rendering for revenue trends, segment distributions, and RFM profiles."),
    ("TanStack Query: ",
     "Server-state management, caching, and processing-job status polling."),
    ("Docker Compose: ",
     "Local PostgreSQL instance and supporting services for development."),
    ("Parquet: ",
     "Columnar storage for processed analytical datasets produced by the Spark engine."),
]
for label, desc in tech:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    r1 = p.add_run(label)
    r1.bold = True
    p.add_run(desc)

# ===========================================================================
# 5. RESULTS
# ===========================================================================
heading("5. Results")
body(
    "The pipeline was executed end-to-end on a deterministic synthetic demo dataset "
    "modelled on the UCI Online Retail schema (InvoiceNo, StockCode, Description, "
    "Quantity, InvoiceDate, UnitPrice, CustomerID, Country). The dataset contains "
    "10,778 line items from 430 customers spanning January to December 2025 and "
    "deliberately includes cancellation invoices, missing customer identifiers, "
    "duplicate rows, and invalid dates so that validation behaves as it would on real "
    "data. All figures below are produced by the Spark pipeline; no values are hard-coded."
)

subheading("5.1 Data Validation and RFM Computation")
body(
    "The validation stage accounted for every excluded record explicitly. Of 10,778 "
    "input rows, 12 exact duplicates were collapsed, 5 rows had unparseable invoice "
    "dates, 181 rows had no customer identifier, 243 cancellation or return lines were "
    "excluded from customer metrics, and 18 lines had non-positive quantities or "
    "prices. This left 10,321 valid transaction lines across 430 segmentable "
    "customers. The captured pipeline output is shown below:"
)
code_block([
    "CustomerIQ data-engine pipeline - demo dataset",
    "Spark 4.2.1 | deterministic seed = 42",
    "",
    "[1/5] Reading dataset: demo_online_retail.csv",
    "Data-quality report",
    "-------------------",
    "  Total rows read            :   10,778",
    "  Exact duplicates removed   :       12",
    "  Invalid invoice dates      :        5",
    "  Missing customer ID        :      181",
    "  Cancellation/return lines :      243",
    "  Non-positive quantity      :        3",
    "  Non-positive unit price    :       15",
    "  Valid transaction lines    :   10,321",
    "  Distinct segmentable cust. :      430",
    "  Transaction window         : 2025-01-02 .. 2025-12-28",
    "",
    "[2/5] RFM computation (analysis reference date = 2025-12-29)",
    "  Customers scored: 430",
    "  RFM sample (first 8 customers by ID):",
    "CustomerID   | Recency (days) | Frequency  | Monetary     | Avg order value",
    "-------------+----------------+------------+--------------+----------------",
    "12018        | 30             | 6          | 249.37       | 41.56",
    "12070        | 13             | 3          | 137.86       | 45.95",
    "12106        | 10             | 12         | 641.67       | 53.47",
    "12116        | 299            | 3          | 47.90        | 15.97",
    "12212        | 27             | 21         | 1,752.25     | 83.44",
    "12235        | 42             | 3          | 84.61        | 28.20",
    "12256        | 126            | 9          | 457.27       | 50.81",
    "12305        | 136            | 4          | 75.66        | 18.92",
], console=True)

subheading("5.2 K-Means Segmentation")
body(
    "The silhouette score was computed for cluster counts from k = 3 to k = 8 using a "
    "fixed random seed of 42. The highest silhouette score of 0.6412 was obtained at "
    "k = 4, which was therefore selected. The four clusters were profiled on the "
    "original RFM scale and mapped to business segments by ranking them on the "
    "composite score z(Frequency) + z(Monetary) - z(Recency):"
)
code_block([
    "[3/5] K-Means clustering (Spark MLlib)",
    "  Feature pipeline: log1p(Frequency), log1p(Monetary), StandardScaler(withMean, withStd)",
    "  Silhouette score by k:",
    "    k=3: 0.6093",
    "    k=4: 0.6412",
    "    k=5: 0.5964",
    "    k=6: 0.5769",
    "    k=7: 0.6297",
    "    k=8: 0.6284",
    "  Selected k = 4 (highest silhouette = 0.6412)",
    "",
    "[4/5] Cluster profiling and segment labeling",
    "  Cluster profiles (original RFM scale):",
    "Cluster  | Customers  | Avg recency (d) | Avg frequency | Avg monetary",
    "---------+------------+-----------------+---------------+-------------",
    "0        | 71         | 21.20           | 2.52          | 88.68",
    "1        | 84         | 27.90           | 18.87         | 1,692.52",
    "2        | 81         | 288.80          | 2.89          | 81.29",
    "3        | 194        | 78.80           | 7.60          | 352.78",
    "  Label mapping (ranked by z(Frequency) + z(Monetary) - z(Recency)):",
    "    cluster 0 -> New Customers",
    "    cluster 1 -> Champions",
    "    cluster 2 -> Hibernating",
    "    cluster 3 -> Potential Loyalists",
], console=True)
body(
    "The recovered segments match the behavioural structure of the demo population: "
    "cluster 1 concentrates high-frequency, high-value customers, while cluster 2 "
    "captures customers whose last purchase was on average 289 days before the "
    "reference date. The distribution of customers across the four segments is shown "
    "below."
)
picture(ASSETS / "fig1_segment_distribution.png", 5.5)

subheading("5.3 Segment Business Insights")
body(
    "Each segment was summarised with its size, revenue contribution, and average RFM "
    "metrics. The Champions segment, 19.5% of customers, generated 63.6% of total "
    "revenue (142,172 of 223,491), while the Hibernating segment contributed only 2.9% "
    "despite representing 18.8% of the customer base. These results demonstrate the "
    "core business value of the platform: retention effort can be prioritised towards "
    "the segments where revenue is concentrated and win-back campaigns can target the "
    "long-inactive Hibernating group."
)
code_block([
    "[5/5] Segment summaries (silhouette = 0.6412)",
    "Segment              | Customers  | % cust.  | Revenue      | % rev.  | Avg spend  | Avg freq  | Avg rec. d",
    "---------------------+------------+----------+--------------+---------+------------+-----------+-----------",
    "Champions            | 84         | 19.50    | 142,171.69   | 63.60   | 1,692.52   | 18.87     | 27.90",
    "Potential Loyalists  | 194        | 45.10    | 68,438.39    | 30.60   | 352.78     | 7.60      | 78.80",
    "Hibernating          | 81         | 18.80    | 6,584.38     | 2.90    | 81.29      | 2.89      | 288.80",
    "New Customers        | 71         | 16.50    | 6,296.07     | 2.80    | 88.68      | 2.52      | 21.20",
], console=True)
body(
    "Total revenue by segment is ranked below. The steep drop from Champions to the "
    "remaining segments is typical of retail datasets and is immediately visible in "
    "the dashboard's Revenue by Segment view."
)
picture(ASSETS / "fig2_revenue_by_segment.png", 6.0)
body(
    "Finally, the average RFM metrics of each segment, indexed to the overall customer "
    "average (100), confirm that the segments are well separated on all three "
    "dimensions. Champions index far above average on Frequency and Monetary, "
    "Hibernating falls far below on Recency (that is, they are much older), and New "
    "Customers are recent but low-volume, exactly as their profiles imply."
)
picture(ASSETS / "fig3_rfm_profiles.png", 5.5)

# ===========================================================================
# 6. CONCLUSION
# ===========================================================================
heading("6. Conclusion")
body(
    "Thus, we studied customer analytics techniques and implemented RFM-based customer "
    "segmentation as our mini-project. The system computes Recency, Frequency, and "
    "Monetary metrics for every customer using distributed PySpark aggregations, "
    "segments customers with the K-Means algorithm from Spark MLlib after justified "
    "log transformation and standard scaling, and evaluates cluster quality with the "
    "silhouette score. Arbitrary cluster identifiers are mapped to interpretable "
    "business segments, and all results are persisted in PostgreSQL and Parquet and "
    "exposed through a versioned REST API and a React analytics dashboard.\n"
    "\n"
    "The end-to-end run on the demo dataset demonstrated that the platform produces "
    "trustworthy, reproducible analytics. Validation transparently accounted for "
    "duplicates, cancellations, missing identifiers, and invalid dates instead of "
    "silently discarding data. The silhouette criterion selected four well-separated "
    "clusters (silhouette = 0.6412), and the resulting segments told a clear business "
    "story: 19.5% of customers (Champions) produced 63.6% of revenue, while a "
    "Hibernating group with an average recency of 289 days contributed under 3% and "
    "represents the primary win-back target. Because the random seed, analysis "
    "reference date, and validation policy are all explicit, the analysis can be "
    "re-run on new datasets and compared against historical runs.\n"
    "\n"
    "Future enhancements could include comparing K-Means against density-based and "
    "hierarchical clustering, adding automated feature engineering and cohort "
    "retention analysis, streaming ingestion for near-real-time segmentation, and "
    "integrating campaign outcome tracking to measure the revenue impact of "
    "segment-targeted marketing."
)

# ===========================================================================
# 7. REFERENCES
# ===========================================================================
heading("7. References")
refs = [
    '1. Han, J., Kamber, M., and Pei, J. "Data Mining: Concepts and Techniques." '
    "3rd Edition, Morgan Kaufmann Publishers, 2011.",
    '2. Lloyd, S. "Least Squares Quantization in PCM." IEEE Transactions on '
    "Information Theory, Vol. 28, No. 2, pp. 129-137, 1982.",
    '3. Kaufman, L., and Rousseeuw, P. J. "Finding Groups in Data: An Introduction '
    'to Cluster Analysis." John Wiley & Sons, 1990.',
    "4. Apache Spark Documentation: MLlib - Clustering (K-Means). "
    "https://spark.apache.org/docs/latest/ml-clustering.html",
    "5. UCI Machine Learning Repository: Online Retail Dataset. "
    "https://archive.ics.uci.edu/ml/datasets/online+retail",
    "6. FastAPI Documentation. https://fastapi.tiangolo.com/",
    "7. React Documentation. https://react.dev/",
    '8. Hughes, A. M. "Strategic Database Marketing." McGraw-Hill, 1996.',
]
for ref in refs:
    body(ref)

# drop the original template's chart images (now unreferenced) to keep the
# package clean; the three new figures are referenced by the new body
for rId in ["rId6", "rId7", "rId8"]:
    rel = doc.part.rels.get(rId)
    if rel is not None and "image" in rel.reltype:
        doc.part.drop_rel(rId)

doc.save(str(DST))
print(f"Saved: {DST}")
print(f"Paragraphs: {len(doc.paragraphs)}")
