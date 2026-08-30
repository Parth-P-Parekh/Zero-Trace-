"""A dummy RAG corpus — the kind of thing a government agency's vector store holds."""
A1, A2 = "718190937865", "997543231948"
DOCS = [
 dict(id="doc-benefits-faq", text=(
   "Employee benefits FAQ. Staff may claim travel reimbursement within 30 days. "
   "Contact the HR desk for the current per-diem rates.")),
 dict(id="doc-payslip-rkumar", text=(
   "PAYSLIP — Rajesh Kumar, Employee ID EMP-4417, Designation Section Officer. "
   "Gross salary 84,500 INR. PAN ABCPZ1234C. Bank credit to account ending 7781. "
   "Deductions: PF 10,140, TDS 6,200.")),
 dict(id="doc-clinical-note", text=(
   "Clinical note, District Hospital. Patient Sunita Devi, Aadhaar " + A1 + ", "
   "presented with Type 2 diabetes mellitus, HbA1c 8.4%. Prescribed metformin 500mg BD. "
   "Follow-up in 6 weeks with the endocrinology unit.")),
 dict(id="doc-tender-public", text=(
   "Tender notice 2026/PWD/114 for road resurfacing, ward 12. "
   "Estimated value 2.4 crore. Bids close 30 September.")),
 dict(id="doc-citizen-record", text=(
   "Citizen services record. Applicant Meena Iyer, Aadhaar " + A2 + ", "
   "PAN ABCPZ1234C, pincode 560103, ration card BPL-88213, "
   "application for subsidy under scheme PMAY-G.")),
 dict(id="doc-infosec-incident", text=(
   "INCIDENT-2026-08. Unauthorised access attempt on the revenue portal. "
   "Root cause: leaked credential AKIAIOSFODNN7EXAMPLE committed to a public repo. "
   "Remediation: key rotated, repo scrubbed.")),
 dict(id="doc-runbook", text=(
   "Deploy runbook. Export DB_PASSWORD=Pr0dRunb00k!2026 then run alembic upgrade head. "
   "Connection: postgres://svc_deploy:Pr0dRunb00k!2026@10.0.4.11:5432/revenue")),
 dict(id="doc-org-chart", text=(
   "Directorate structure. Citizen Services, Revenue, HR & Personnel, InfoSec. "
   "Each directorate reports to the Director (Administration).")),
]

def retrieve(query: str, k: int = 8):
    """Deliberately dumb 'vector' search: keyword overlap, like a real retriever it
    returns what is *near*, not what the caller is entitled to."""
    q = set(query.lower().split())
    scored = [(len(q & set(d["text"].lower().split())), d) for d in DOCS]
    scored.sort(key=lambda x: -x[0])
    return [d for _, d in scored[:k]]
