```
[Client] --> Bubble.io Front-end
|                 |
| GraphQL (auth)  | REST (ledger)
[AuthN/AuthZ] <----> [Ledger API] <----> [PostgreSQL + Hash-chain]
| MFA, SCIM       | append-only tx   |
|                 V                  |
|            [Trust Graph]           |
|                 ↑ Neo4j            |
+--> S3 (evidence blobs)             |
↑                |
AI-Explain API ---------->+
```  
- **Zero-Trust Gatekeeper** – Cloudflare Access in front of Bubble; RBAC + MFA.  
- **Ledger API** – All writes append SHA-256 hash; daily Merkle root hashed to Arweave.  
- **Trust Graph** – Neo4j node types: `Member`, `Badge`, `Vote`, `Alert`.  
- **Explainable-AI Wrapper** – Every Gen-AI response returns JSON `{answer, sources[], confidence}`.  
---