import { useState, useEffect, useRef } from 'react';
import { AlertTriangle, XCircle, FileText, CheckCircle2, BarChart3, ShieldCheck, LogOut, User as UserIcon, KeyRound } from 'lucide-react';

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

interface UserIdentity {
  id: string;
  username: string;
  role: string;
}

function App() {
  // --- Auth & Identity State ---
  const [currentUser, setCurrentUser] = useState<UserIdentity | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const[password, setPassword] = useState("");
  
  const [authError, setAuthError] = useState<string | null>(null);
  const [authSuccess, setAuthSuccess] = useState<string | null>(null);
  
  // FIX: Split Loading States
  const [authLoading, setAuthLoading] = useState(false);
  const [auditLoading, setAuditLoading] = useState(false);
  
  // FIX: Deterministic State Machine (Wait for backend before showing UI)
  const [isInitializing, setIsInitializing] = useState(true); 

  // --- App State ---
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [selectedPolicy, setSelectedPolicy] = useState<string>("");
  const[query, setQuery] = useState("");
  const [result, setResult] = useState<AuditResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // FIX: Resilience & Anti-Spam Refs
  const abortControllerRef = useRef<AbortController | null>(null);
  const lastAuditTimeRef = useRef<number>(0);

  const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

  // --- 1. Application Bootstrap (On Load) ---
  useEffect(() => {
    // FIX: Single network call to get Identity AND Policies securely via httpOnly Cookie
    fetch(`${API_URL}/auth/bootstrap`, { credentials: 'include' })
      .then(async res => {
        if (res.status === 401 || res.status === 403) {
          throw new Error("No active session");
        }
        if (!res.ok) throw new Error("Failed to bootstrap application");
        return res.json();
      })
      .then(data => {
        setCurrentUser(data.user);
        setPolicies(data.policies);
        setIsInitializing(false);
      })
      .catch(err => {
        console.log("Bootstrap:", err.message); // Expected if not logged in
        setCurrentUser(null);
        setIsInitializing(false);
      });
  },[API_URL]);

  // --- 2. Authentication Handlers ---
  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    setAuthError(null);
    setAuthSuccess(null);

    try {
      if (authMode === "register") {
        const response = await fetch(`${API_URL}/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password })
        });
        
        if (!response.ok) {
          // FIX: Deep Error Parsing
          const errData = await response.json().catch(() => ({}));
          throw new Error(errData.detail || "Registration failed");
        }
        
        setAuthSuccess("Account created successfully! Please log in.");
        setAuthMode("login");
        setPassword(""); 
        
      } else {
        const formData = new URLSearchParams();
        formData.append("username", username);
        formData.append("password", password);

        // FIX: credentials: 'include' tells the browser to accept the httpOnly cookie
        const response = await fetch(`${API_URL}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: formData,
          credentials: 'include' 
        });

        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          throw new Error(errData.detail || "Invalid username or password");
        }

        // Login successful! Now fetch the bootstrap data to populate the app
        const bootstrapRes = await fetch(`${API_URL}/auth/bootstrap`, { credentials: 'include' });
        if (bootstrapRes.ok) {
            const data = await bootstrapRes.json();
            setCurrentUser(data.user);
            setPolicies(data.policies);
        }
      }
    } catch (err: any) {
      setAuthError(err.message);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = async () => {
    await fetch(`${API_URL}/auth/logout`, { method: 'POST', credentials: 'include' }).catch(() => {});
    setCurrentUser(null);
    setPolicies([]);
    setResult(null);
    setQuery("");
    
    // FIX: Cancel pending audits on logout
    if (abortControllerRef.current) abortControllerRef.current.abort();
  };

  // --- 3. Execute Audit (With Retry, Abort & Anti-Spam) ---
  const handleAudit = async () => {
    // FIX: Anti-Spam Cooldown (3 seconds)
    const now = Date.now();
    if (now - lastAuditTimeRef.current < 3000) {
      setError("Please wait a moment before submitting another audit.");
      return;
    }
    lastAuditTimeRef.current = now;

    // FIX: Request Cancellation
    if (abortControllerRef.current) abortControllerRef.current.abort();
    abortControllerRef.current = new AbortController();

    setAuditLoading(true);
    setResult(null);
    setError(null);
    
    // FIX: Network Retry Logic (1 Retry for transient errors)
    let attempts = 0;
    const maxAttempts = 2;

    while (attempts < maxAttempts) {
      try {
        const response = await fetch(`${API_URL}/audit`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include', // Automatically sends the httpOnly cookie
          body: JSON.stringify({ query, policy_id: selectedPolicy || null }),
          signal: abortControllerRef.current.signal
        });
        
        if (response.status === 401 || response.status === 403) {
          await handleLogout();
          throw new Error("Session expired. Please log in.");
        }

        if (!response.ok) {
          // FIX: Deep error parsing
          const errData = await response.json().catch(() => ({}));
          throw new Error(errData.detail || `Server Error: ${response.statusText}`);
        }

        const data = await response.json();
        setResult(data);
        break; // Success! Break the retry loop.

      } catch (err: any) {
        if (err.name === 'AbortError') return; // Cancelled by user gracefully
        
        attempts++;
        if (attempts >= maxAttempts || err.message.includes("Session expired")) {
          console.error("Audit failed finally", err);
          setError(err.message || "An unexpected error occurred.");
          break;
        }
        console.warn(`Audit attempt ${attempts} failed, retrying...`);
        await new Promise(r => setTimeout(r, 1000)); // 1s exponential backoff
      }
    }
    setAuditLoading(false);
  };

  // --- Helpers ---
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'PASS': return 'bg-emerald-50 text-emerald-900 border-emerald-200';
      case 'FAIL': return 'bg-rose-50 text-rose-900 border-rose-200';
      case 'AMBIGUOUS': return 'bg-amber-50 text-amber-900 border-amber-200';
      default: return 'bg-slate-50 text-slate-900 border-slate-200';
    }
  };

  const getIntentBadge = (intent: string) => {
    switch (intent) {
      case 'COMPLIANCE_AUDIT': return 'bg-purple-100 text-purple-800 border-purple-200';
      case 'SYSTEM_METADATA': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'REJECT': return 'bg-gray-100 text-gray-800 border-gray-200';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  // ==========================================
  // VIEW: INITIALIZING SCREEN
  // ==========================================
  if (isInitializing) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center">
        <div className="h-8 w-8 border-4 border-blue-600/30 border-t-blue-600 rounded-full animate-spin mb-4"></div>
        <p className="text-slate-500 font-medium animate-pulse">Verifying secure session...</p>
      </div>
    );
  }

  // ==========================================
  // VIEW: AUTHENTICATION SCREEN
  // ==========================================
  if (!currentUser) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4 selection:bg-blue-100 animate-fade-in">
        <div className="bg-white max-w-md w-full p-8 rounded-2xl shadow-xl border border-slate-200">
          <div className="flex flex-col items-center mb-8">
            <div className="h-16 w-16 bg-[#0B1120] rounded-xl flex items-center justify-center mb-4 shadow-lg">
              <ShieldCheck className="h-8 w-8 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">OmniCompliance</h1>
            <p className="text-sm text-slate-500 font-medium mt-1">
              {authMode === 'login' ? 'Sign in to your auditor account' : 'Create an auditor account'}
            </p>
          </div>

          <form onSubmit={handleAuth} className="space-y-5">
            <div>
              <label className="block text-sm font-semibold text-slate-900 mb-1.5">Username</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <UserIcon className="h-4 w-4 text-slate-400" />
                </div>
                <input 
                  type="text" 
                  required
                  className="w-full pl-10 pr-3 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-600 focus:border-blue-600 transition-colors"
                  placeholder="Enter your username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-semibold text-slate-900 mb-1.5">Password</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <KeyRound className="h-4 w-4 text-slate-400" />
                </div>
                <input 
                  type="password" 
                  required
                  className="w-full pl-10 pr-3 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-600 focus:border-blue-600 transition-colors"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
            </div>

            {authError && (
              <div className="p-3 bg-red-50 text-red-700 text-sm rounded-md border border-red-200 flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                {authError}
              </div>
            )}

            {authSuccess && (
              <div className="p-3 bg-emerald-50 text-emerald-700 text-sm rounded-md border border-emerald-200 flex items-start gap-2">
                <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0" />
                {authSuccess}
              </div>
            )}

            <button 
              type="submit"
              disabled={authLoading}
              className="w-full bg-[#0B1120] hover:bg-slate-800 text-white font-semibold py-2.5 rounded-lg transition-all shadow-md disabled:opacity-70 flex justify-center items-center"
            >
              {authLoading ? (
                <span className="flex items-center gap-2">
                  <div className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                  Processing...
                </span>
              ) : (authMode === 'login' ? "Sign In" : "Register")}
            </button>
          </form>

          <div className="mt-6 text-center">
            <button 
              onClick={() => {
                setAuthMode(authMode === 'login' ? 'register' : 'login');
                setAuthError(null);
                setAuthSuccess(null);
              }}
              className="text-sm font-semibold text-blue-600 hover:text-blue-800 transition-colors"
            >
              {authMode === 'login' ? "Need an account? Register" : "Already have an account? Sign in"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ==========================================
  // VIEW: MAIN DASHBOARD
  // ==========================================
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans selection:bg-blue-100 animate-fade-in">
      
      <nav className="bg-white border-b border-slate-200 px-6 py-3 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 bg-[#0B1120] rounded-lg flex items-center justify-center shadow-sm">
              <ShieldCheck className="h-5 w-5 text-white" />
            </div>
            <span className="text-slate-900 font-bold text-xl tracking-tight">Omni<span className="font-light text-slate-500">Compliance</span></span>
            {currentUser?.role && (
              <span className="ml-2 text-[10px] font-bold px-2 py-0.5 bg-blue-50 text-blue-700 rounded border border-blue-100 uppercase tracking-wider hidden sm:inline-block">
                {currentUser.role} Portal
              </span>
            )}
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-sm font-medium text-slate-600 bg-slate-50 px-3 py-1.5 rounded-full border border-slate-200">
              <UserIcon className="h-4 w-4 text-slate-400" />
              {/* FIX: Actually show the user's identity! */}
              <span className="hidden sm:inline-block font-semibold">{currentUser.username}</span>
            </div>
            <button 
              onClick={handleLogout}
              className="text-slate-500 hover:text-rose-600 transition-colors p-2 rounded-full hover:bg-rose-50"
              title="Sign Out"
            >
              <LogOut className="h-5 w-5" />
            </button>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto p-6 grid grid-cols-1 lg:grid-cols-12 gap-8 mt-4">
        
        <div className="lg:col-span-4 space-y-6">
          <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
            <h2 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-6 flex items-center gap-2">
              <BarChart3 className="h-4 w-4" /> Audit Configuration
            </h2>
            
            <div className="space-y-6">
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
              </div>

              <div>
                <label className="block text-sm font-semibold text-slate-900 mb-2">Regulatory Obligation</label>
                <textarea 
                  className="w-full p-3 bg-slate-50 border border-slate-300 text-slate-900 text-sm rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-blue-600 h-32 resize-none transition-shadow"
                  placeholder="e.g., Does this policy require annual testing?"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </div>

              {error && (
                <div className="p-3 bg-red-50 text-red-700 text-sm rounded-md border border-red-200 flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                  {error}
                </div>
              )}

              <button 
                onClick={handleAudit}
                disabled={auditLoading || !query}
                className="w-full bg-[#0B1120] hover:bg-slate-800 text-white font-semibold py-3 px-4 rounded-lg transition-all shadow-md hover:shadow-lg disabled:opacity-50 disabled:shadow-none flex justify-center items-center gap-2 group"
              >
                {auditLoading ? (
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

        <div className="lg:col-span-8">
          {result ? (
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden animate-fade-in">
              <div className={`p-5 border-b flex justify-between items-center ${getStatusColor(result.status)}`}>
                <div className="flex items-center gap-3">
                  {result.status === 'PASS' && <CheckCircle2 className="h-8 w-8"/>}
                  {result.status === 'FAIL' && <XCircle className="h-8 w-8"/>}
                  {result.status === 'AMBIGUOUS' && <AlertTriangle className="h-8 w-8"/>}
                  {result.status === 'INCONCLUSIVE' && <AlertTriangle className="h-8 w-8"/>}
                  <div>
                    <h3 className="text-2xl font-bold tracking-tight">{result.status}</h3>
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