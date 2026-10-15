ART INDIA HACKATHON 2026
Kavach: Computer Vision Integrity Assurance Framework
PS Code: SIH26228
Ministry / Organization Name: Ministry of Defence MoD, Indian Army DGIS
Problem Statement Title: Trustworthy Computer Vision Integrity Assurance
for Data, Models and Inference Outputs in Multi-Contributor Pipelines
Team Name: Annihilator
Team Leader Name: Harshit Kandpal
Institute Name: IIT Bhilai Indian Institute of Technology, Bhilai)
Theme Name: Blockchain & Cybersecurity
Kavach: Computer Vision Integrity Assurance Framework
THE PROBLEM
● Unvetted Pipelines: Multi-vendor data & 3rd-party models enter unverified.
● Hidden Vulnerabilities: No guarantee against data poisoning or backdoor weights.
● Zero Device Proof: Lacks cryptographic verification for edge outputs & hardware integrity.
● Fragmented Checks: Disconnected lifecycle stages reliant on manual, unsigned reviews.
OUR SOLUTION
● Pre-Deployment Gating: Automated screening of datasets & models prior to ingestion.
● Active Edge Protection: Real-time drift assessment, input sanitization, & signed inferences.
● Tamper-Evident Ledger: End-to-end event chaining in an audit-ready, verifiable log.
● Air-Gapped & Agnostic: Fully offline operation with zero cloud infrastructure dependence.
UNIQUENESS
Evidence over verdict
Platt-calibrated, continuous score vs binary
pass/fail
Hardware-bound trust
Cryptographic keys sealed directly to TPM 2.0
PCRs
Evidence Bus
Unified append-only, hash-chained audit log
Risk ≠ missing metadata
Provenance completeness scored independently
Non-compensatory fusion
A passing metric can never mask a failed check Explicit unavailability
Zero skipped checks; unassessed steps flagged
Flow Diagram
1 · Dataset & model intake
COCO · YOLO · PyTorch · TorchScript · ONNX
2 · Integrity screening
M1 data · M2 model (white/black-box)
3 · Gatekeeping decision
Accept · Review · Quarantine → remediate
4 · Live input sanitisation
M4 drift attribution + Feature Squeezing
5 · Attested signed inference
PCR-sealed Ed25519 key → signed record
6 · Ledger & governance review
Merkle checkpoints · M5 reports · verifier
Assesses: Artifact Integrity · Behavioural Integrity · Inference
Provenance
2
TECHNICAL APPROACH
1 · Intake: Sandboxed adapters
hash COCO/YOLO/PyTorch/ONNX
files into a SHA256 manifest.
2 · Screen: Spectral, Confident
Learning, k-NN, Neural Cleanse,
and STRIP test data and models.
3 · Gate: Accept, Review or
Quarantine; quarantined items are
remediated and fully re-screened.
4 · Sanitise: Drift attribution +
Feature Squeezing clean live
input.
5 · Attest: TPM PCR-sealed
Ed25519 key signs every
inference.
6 · Govern: Appends to the
Evidence Bus; Merkle
checkpoints, verifier and reports.
Assurance Levels:
• A TPM 2.0 PCR-sealed key, full
confidence.
• B Software signing, no TPM; reduced
confidence cap.
• C Unsigned/unattested; evidence
only, cannot support Accept.
HOW IT WORKS
FEASIBILITY AND VIABILITY
TECHNICAL OPERATIONAL
● Air-Gapped: Fully air-gapped with
all dependencies vendored.
● COTS Hardware: Runs on
standard COTS edge and server
hardware.
USERS SCALABILITY
CHALLENGES AND
HOW WE RESOLVE
THEM
5
● Benchmark Proven: All core
techniques published &
benchmarked.
● Novel Integration: System-level
integrity orchestration.
● Defence CV Operators and
ATR tactical integrators.
● Multi-Party ML Pipeline
owners, regulators & auditors.
● Roadmap: MVP  TPM/HSM →
Ledger → ZK.
● Evidence Bus: Modular
pipelines allow zero-friction
extensions.
POTENTIAL CHALLENGE RESOLUTION
Trusted Platform Module (TPM) 2.0 unavailable Software signing with trust_anchor label, Level B tier and a 0.60 score cap
Black-box access only STRIP fallback; white-box checks reported as "assessment unavailable"
Zero-day attacks outside our detectors Published Coverage Statement; declared limits include adaptive triggers, compromised keys, side-channels
& extraction
Signing overhead at scale Ed25519; Platform Configuration Register (PCR)-sealed key with periodic quotes, not per-inference quotes
Multi-party trust boundaries Contributor Risk Score and Admission Gatekeeper isolation
Missing metadata Provenance Completeness scored separately from risk
Untrusted model files Sandboxed, network-less loading with restricted deserialisation
Flagged artifacts Quarantine, Fine-Pruning or relabelling, re-hash, full re-screen
Standards alignment Zero Trust Architecture (NIST SP 800−207) and NIST Artificial Intelligence (AI) 100−2
IMPACT AND BENEFITS
6
KEY VALUE DRIVERS
Cryptographic Trust
100% hardware-bound inference
signing via Trusted Platform Module
TPM 2.0 Platform Configuration
Registers PCRs. Guarantees
tamper-evident execution logs.
Proactive Gating
Blocks Trojan backdoors, poisoned
datasets, and weight manipulations
pre-deployment through automated
screening filters.
Zero Cloud Cost
Fully air-gapped execution on
standard Commercial Off-The-Shelf
COTS) edge hardware with zero
external cloud dependencies or
fees.
NIST Compliance
Strict alignment with National
Institute of Standards and
Technology NIST Special
Publication SP 800207 Zero Trust
Architecture.
RESEARCH AND REFERENCES
Spectral Signatures — NeurIPS 18
Activation Clustering — AAAI 19
Confident Learning — JAIR 2021
Mahalanobis OOD — NeurIPS 2018
Deep k-NN OOD — ICML 2022
Neural Cleanse — IEEE S&P 2019
STRIP Defence — ACSAC 2019
Fine-Pruning — RAID 2018
ABS Brain Stim. — ACM CCS 2019
RFC 6962 Cert Transparency — IETF
Sigstore Rekor Log — Sigstore
Atlas: ML Provenance — 2025
Feature Squeezing — NDSS 18
Platt scaling — SVMs, 1999
NIST SP 800207 — Zero Trust
NIST AI 1002 — Adv ML Taxonomy
TOOLS Cleanlab · Adversarial Robustness Toolbox · FAISS
BENCHMARKS BackdoorBench Wu et al., NeurIPS 2022 · NIST TrojAI · OpenOOD v1.5
EVALUATION PLAN public or synthetic data only COCO subsets, CIFAR10, GTSRB, Tiny-ImageNet, YOLO; metrics include detection rate, false rejection STRIP ≤
1%, attack success before/after remediation, calibration error, signing latency, & verification tim