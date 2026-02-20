import { useState, useEffect } from 'react';
import { AlertTriangle, XCircle, Search, FileText, CheckCircle2, BarChart3, Lock, ShieldCheck } from 'lucide-react';

// --- Types ---
interface Policy {
  id: string;
  name: string;
}

interface AuditResult {
  status: "PASS" | "FAIL" | "AMBIGUOUS" | "INCONCLUSIVE";
  confidence: "HIGH" | "MEDIUM" | "LOW";
  reasoning: string;
  citations: string[];
  intent: string;
}

function App() {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [selectedPolicy, setSelectedPolicy] = useState<string>("");
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<AuditResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // --- 1. Fetch Policies on Load ---
  useEffect(() => {
    fetch('http://localhost:8000/policies')
      .then(res => res.json())
      .then(data => setPolicies(data))
      .catch(err => {
        console.error("API Error:", err);
        setError("Failed to load policies. Is the backend running?");
      });
  }, []);

  // --- 2. Execute Audit ---
  const handleAudit = async () => {
    setLoading(true);
    setResult(null);
    setError(null);
    
    try {
      const response = await fetch('http://localhost:8000/audit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          query, 
          policy_id: selectedPolicy || null 
        })
      });
      
      if (!response.ok) {
        throw new Error(`Server Error: ${response.statusText}`);
      }

      const data = await response.json();
      setResult(data);
    } catch (err: any) {
      console.error("Audit failed", err);
      setError(err.message || "An unexpected error occurred during the audit.");
    } finally {
      setLoading(false);
    }
  };

  // --- Helper: Status Styles ---
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'PASS': return 'bg-emerald-50 text-emerald-900 border-emerald-200';
      case 'FAIL': return 'bg-rose-50 text-rose-900 border-rose-200';
      case 'AMBIGUOUS': return 'bg-amber-50 text-amber-900 border-amber-200';
      default: return 'bg-slate-50 text-slate-900 border-slate-200';
    }
  };

  // --- Helper: Intent Badge Styles ---
  const getIntentBadge = (intent: string) => {
    switch (intent) {
      case 'COMPLIANCE_AUDIT': return 'bg-purple-100 text-purple-800 border-purple-200';
      case 'SYSTEM_METADATA': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'REJECT': return 'bg-gray-100 text-gray-800 border-gray-200';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans selection:bg-blue-100">
      
      {/* --- BRANDED NAVBAR --- */}
      <nav className="bg-white border-b border-slate-200 px-6 py-3 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img src="/public/bal-logo2.jpeg" alt="BAL Logo" className="h-16 w-16 object-contain rounded-lg" onError={(e) => e.currentTarget.style.display = 'none'} />
            <span className="text-slate-900 font-bold text-xl tracking-tight">Omni<span className="font-light text-slate-500">Compliance</span></span>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-xs font-semibold px-2 py-1 bg-blue-50 text-blue-700 rounded border border-blue-100">
              v1.0
            </span>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto p-6 grid grid-cols-1 lg:grid-cols-12 gap-8 mt-4">
        
        {/* --- LEFT PANEL: CONTROL CENTER --- */}
        <div className="lg:col-span-4 space-y-6">
          <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
            <h2 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-6 flex items-center gap-2">
              <BarChart3 className="h-4 w-4" /> Audit Configuration
            </h2>
            
            <div className="space-y-6">
              {/* Policy Selector */}
              <div>
                <label className="block text-sm font-semibold text-slate-900 mb-2">Scope</label>
                <div className="relative">
                  <select 
                    className="w-full pl-3 pr-10 py-2.5 bg-slate-50 border border-slate-300 text-slate-900 text-sm rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-blue-600 block transition-shadow"
                    value={selectedPolicy}
                    onChange={(e) => setSelectedPolicy(e.target.value)}
                  >
                    <option value="">Global Search (All Policies)</option>
                    {policies.map(p => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                </div>
                <p className="mt-2 text-xs text-slate-500 flex items-center gap-1">
                  {selectedPolicy ? <Lock className="h-3 w-3"/> : <Search className="h-3 w-3"/>}
                  {selectedPolicy ? "Scoped to specific document." : "Searching entire knowledge base."}
                </p>
              </div>

              {/* Query Input */}
              <div>
                <label className="block text-sm font-semibold text-slate-900 mb-2">Regulatory Obligation</label>
                <textarea 
                  className="w-full p-3 bg-slate-50 border border-slate-300 text-slate-900 text-sm rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-blue-600 h-32 resize-none transition-shadow"
                  placeholder="e.g., Does this policy require annual testing?"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </div>

              {/* Error Message */}
              {error && (
                <div className="p-3 bg-red-50 text-red-700 text-sm rounded-md border border-red-200 flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                  {error}
                </div>
              )}

              {/* Action Button */}
              <button 
                onClick={handleAudit}
                disabled={loading || !query}
                className="w-full bg-[#0B1120] hover:bg-slate-800 text-white font-semibold py-3 px-4 rounded-lg transition-all shadow-md hover:shadow-lg disabled:opacity-50 disabled:shadow-none flex justify-center items-center gap-2 group"
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <div className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                    Processing...
                  </span>
                ) : (
                  <>Execute Audit <CheckCircle2 className="h-4 w-4 group-hover:scale-110 transition-transform"/></>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* --- RIGHT PANEL: RESULTS --- */}
        <div className="lg:col-span-8">
          {result ? (
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden animate-fade-in">
              {/* Result Header */}
              <div className={`p-5 border-b flex justify-between items-center ${getStatusColor(result.status)}`}>
                <div className="flex items-center gap-3">
                  {result.status === 'PASS' && <CheckCircle2 className="h-8 w-8"/>}
                  {result.status === 'FAIL' && <XCircle className="h-8 w-8"/>}
                  {result.status === 'AMBIGUOUS' && <AlertTriangle className="h-8 w-8"/>}
                  {result.status === 'INCONCLUSIVE' && <AlertTriangle className="h-8 w-8"/>}
                  <div>
                    <h3 className="text-2xl font-bold tracking-tight">{result.status}</h3>
                    {/* Intent Badge */}
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded border uppercase tracking-wider ${getIntentBadge(result.intent)}`}>
                        {result.intent}
                      </span>
                      <p className="text-sm font-medium opacity-80">Compliance Assessment</p>
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs uppercase tracking-wider font-bold opacity-60">Confidence</div>
                  <div className="text-lg font-bold">{result.confidence}</div>
                </div>
              </div>

              {/* Result Body */}
              <div className="p-8 space-y-8">
                <div>
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">Analysis & Reasoning</h3>
                  <div className="prose prose-slate max-w-none text-slate-700 leading-relaxed">
                    {result.reasoning}
                  </div>
                </div>

                <div>
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">Evidence Trail</h3>
                  {result.citations.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {result.citations.map((cite, idx) => (
                        <div key={idx} className="flex items-center gap-2 text-sm font-medium text-blue-700 bg-blue-50 px-3 py-1.5 rounded-full border border-blue-100 hover:bg-blue-100 transition-colors cursor-default">
                          <FileText className="h-3.5 w-3.5" />
                          {cite}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-4 bg-slate-50 border border-slate-100 rounded-lg text-slate-500 text-sm italic">
                      No specific citations were referenced in the final decision.
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="h-full min-h-[400px] flex flex-col items-center justify-center text-slate-300 border-2 border-dashed border-slate-200 rounded-xl bg-slate-50/50">
              <div className="p-4 bg-white rounded-full shadow-sm mb-4">
                <ShieldCheck className="h-10 w-10 text-slate-200" />
              </div>
              <p className="font-medium text-slate-400">Select a policy scope to begin audit.</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;