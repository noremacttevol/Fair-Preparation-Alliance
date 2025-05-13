1. **New joiner creates account** → Gatekeeper issues temp “Outer-Circle” role (read-only).  
2. **Completes Probation Drill** → Bubble workflow calls `POST /badges` → Trust Graph adds `Drill:Pass`.  
3. **Two peers endorse** → Role promoted to “Inner-Circle”; UI shows green firewall ring.  
4. **Any member spots issue** → clicks _Flag_ → `POST /alerts`; squad vote auto-starts.  
5. **Vote-to-Zero passes** → Ledger records revocation; role set to “Suspended”.  
---