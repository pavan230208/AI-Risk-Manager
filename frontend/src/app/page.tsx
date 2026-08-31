"use client";
import React, { useState, useEffect } from "react";

// Types
type TxResult = {
  transaction_id: string;
  ml_probability: number;
  rule_signals: string[];
  final_score: number;
  risk_level: string;
  policy_action: string;
  human_approval_required: boolean;
  authorization_state: string;
  execution_status: string;
  explanation: string;
  timestamp: string;
};

type Tx = {
  transaction_id: string;
  user_id: string;
  merchant_id: string;
  amount: number;
  currency: string;
  device_id: string;
  location: string;
  timestamp: string;
};

type FeedItem = {
  tx: Tx;
  result: TxResult;
  status: string; // "PENDING", "SAFE / HUMAN APPROVED", "NOT SAFE / HUMAN REJECTED", "PROCESSED"
};

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<"dashboard" | "manual" | "model" | "impact" | "system">("dashboard");
  const [mlMetrics, setMlMetrics] = useState<any>(null);
  
  // Dashboard states
  const [autoRunning, setAutoRunning] = useState(false);
  const [autoStats, setAutoStats] = useState({
    total: 0, analyzed: 0, low: 0, medium: 0, high: 0, allowed: 0, flagged: 0, blocked: 0, pendingReview: 0
  });
  
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<FeedItem[]>([]);
  const [resolvedApprovals, setResolvedApprovals] = useState<(FeedItem & { action: "APPROVE" | "REJECT" })[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  
  // Right Column Search States
  const [searchQueue, setSearchQueue] = useState("");
  const [searchApproved, setSearchApproved] = useState("");
  const [searchRejected, setSearchRejected] = useState("");
  const [searchResolved, setSearchResolved] = useState("");
  
  // Manual Analysis state
  const [manualTx, setManualTx] = useState({
    transaction_id: "TXN-" + Math.floor(Math.random() * 100000),
    user_id: "USR-123", merchant_id: "MERCH-456", amount: 50.0,
    currency: "USD", device_id: "DEV-OLD", location: "US",
    timestamp: new Date().toISOString()
  });
  const [manualResult, setManualResult] = useState<TxResult | null>(null);
  const [manualLoading, setManualLoading] = useState("");
  const [manualError, setManualError] = useState("");
  const [scenarioDesc, setScenarioDesc] = useState("Select a scenario to test different risk profiles.");

  const [systemState, setSystemState] = useState<any>(null);
  const [systemError, setSystemError] = useState<string | null>(null);

  // Fetch / Auth
  const getHeaders = (isGet = false) => {
    const headers: any = {
      "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbl91c2VyIiwicm9sZSI6IkFETUlOIiwiZXhwIjoyMDUxMjIyNDAwfQ.PFOWOufUrFWnJ22H_ARkf-Xj8uKjpC2fKDbPMQ-Wx9k",
      "X-API-Key": process.env.NEXT_PUBLIC_API_KEY || process.env.NEXT_PUBLIC_ADMIN_API_KEY || ""
    };
    if (!isGet) headers["Content-Type"] = "application/json";
    return headers;
  };
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  
  const fetchSystemState = async () => {
    try {
      const res = await fetch(`${apiUrl}/api/v1/system/trace`, { headers: getHeaders(true) });
      if (res.ok) {
        setSystemState(await res.json());
        setSystemError(null);
      }
    } catch (e: any) {
      console.warn("Trace fetch skipped:", e.message);
    }

    try {
      const mlRes = await fetch(`${apiUrl}/api/v1/ml/evaluation`, { headers: getHeaders(true) });
      if (mlRes.ok) {
        setMlMetrics(await mlRes.json());
        setSystemError(null);
      }
    } catch (e: any) {
      console.warn("ML eval fetch skipped:", e.message);
    }
  };

  useEffect(() => {
    fetchSystemState();
    const interval = setInterval(fetchSystemState, 3000);
    return () => clearInterval(interval);
  }, []);

  const toggleKillSwitch = async (active: boolean) => {
    await fetch(`${apiUrl}/api/v1/system/kill-switch`, {
      method: "POST", headers: getHeaders(), body: JSON.stringify({ active })
    });
    fetchSystemState();
  };

  // Evaluator function
  const evaluateTx = async (txData: Tx) => {
    const res = await fetch(`${apiUrl}/api/v1/evaluate`, {
      method: "POST", headers: getHeaders(), body: JSON.stringify(txData)
    });
    if (!res.ok) throw new Error("API Error: " + res.status);
    return await res.json();
  };

  // Automated Protection Loop
  useEffect(() => {
    let interval: any;
    if (autoRunning) {
      interval = setInterval(async () => {
        const amounts = [20, 50, 150, 300, 1500, 8000, 32000, 85000];
        const locations = ["US", "US", "US", "UK", "IN", "CN", "RU", "KP"];
        const devices = ["DEV-OLD", "DEV-NEW", "DEV-NEW-HACKED"];
        
        const simTx: Tx = {
          transaction_id: "TXN-" + Math.floor(Math.random() * 1000000),
          user_id: "USR-" + Math.floor(Math.random() * 1000),
          merchant_id: "MERCH-" + Math.floor(Math.random() * 500),
          amount: amounts[Math.floor(Math.random() * amounts.length)],
          currency: "USD",
          device_id: devices[Math.floor(Math.random() * devices.length)],
          location: locations[Math.floor(Math.random() * locations.length)],
          timestamp: new Date().toISOString()
        };

        try {
          const result = await evaluateTx(simTx);
          const needsReview = result.authorization_state === 'PENDING_APPROVAL' || result.policy_action === 'REQUIRE_APPROVAL' || result.policy_action === 'FLAG';
          const newItem: FeedItem = { tx: simTx, result, status: needsReview ? "PENDING" : "PROCESSED" };

          setFeed(prev => [newItem, ...prev].slice(0, 50));
          
          if (needsReview) {
            setPendingApprovals(prev => [newItem, ...prev]);
          }

          setAutoStats(prev => ({
            ...prev,
            total: prev.total + 1,
            analyzed: prev.analyzed + 1,
            low: ['SAFE', 'LOW'].includes(result.risk_level) ? prev.low + 1 : prev.low,
            medium: ['SUSPICIOUS', 'MEDIUM'].includes(result.risk_level) ? prev.medium + 1 : prev.medium,
            high: ['HIGH_RISK', 'CRITICAL', 'HIGH'].includes(result.risk_level) ? prev.high + 1 : prev.high,
            allowed: result.policy_action === 'ALLOW' ? prev.allowed + 1 : prev.allowed,
            flagged: needsReview ? prev.flagged + 1 : prev.flagged,
            blocked: ['BLOCK', 'BLOCK_MERCHANT', 'KILL_SWITCH'].includes(result.policy_action) ? prev.blocked + 1 : prev.blocked,
            pendingReview: needsReview ? prev.pendingReview + 1 : prev.pendingReview
          }));
        } catch (e) { console.error("Sim error", e); }
      }, 3500);
    }
    return () => clearInterval(interval);
  }, [autoRunning]);

  // Handle Human Approval
  const resolveTransaction = async (txId: string, action: "APPROVE" | "REJECT") => {
    try {
      const itemToResolve = pendingApprovals.find(i => i.tx.transaction_id === txId) || resolvedApprovals.find(i => i.tx.transaction_id === txId);
      if (!itemToResolve) return;

      // Optimistic update for instant UI feedback
      const updatedStatus = action === "APPROVE" ? "SAFE / HUMAN APPROVED" : "NOT SAFE / HUMAN REJECTED";
      setPendingApprovals(prev => prev.filter(item => item.tx.transaction_id !== txId));
      setResolvedApprovals(prev => [{ ...itemToResolve, action, status: updatedStatus }, ...prev.filter(i => i.tx.transaction_id !== txId)].slice(0, 50));
      setFeed(prev => prev.map(item => item.tx.transaction_id === txId ? { ...item, status: updatedStatus } : item));
      setAutoStats(prev => ({ ...prev, pendingReview: Math.max(0, pendingApprovals.length - 1) }));

      await fetch(`${apiUrl}/api/v1/transactions/${txId}/resolve`, {
        method: "POST", headers: getHeaders(), body: JSON.stringify({ action, reason: "Human review via Dashboard" })
      });
    } catch(e) {
      console.error("Resolution failed", e);
    }
  };

  const handleManualResolution = async (action: "APPROVE" | "REJECT") => {
    if (!manualResult || !manualTx) return;
    try {
      const newItem: FeedItem = { tx: manualTx as Tx, result: manualResult, status: action === "APPROVE" ? "SAFE / HUMAN APPROVED" : "NOT SAFE / HUMAN REJECTED" };
      setResolvedApprovals(prev => [{ ...newItem, action }, ...prev].slice(0, 50));
      setFeed(prev => [newItem, ...prev].slice(0, 50));
      
      await fetch(`${apiUrl}/api/v1/transactions/${manualTx.transaction_id}/resolve`, {
        method: "POST", headers: getHeaders(), body: JSON.stringify({ action, reason: "Manual analysis direct resolution" })
      });
      setActiveTab("dashboard");
    } catch (e) {
      console.error("Manual resolution failed", e);
    }
  };

  // Manual Analysis
  const runManualAnalysis = async () => {
    setManualLoading("Analyzing..."); setManualError(""); setManualResult(null);
    try {
      const res = await evaluateTx(manualTx);
      setManualResult(res);
    } catch (e: any) { setManualError(e.message); }
    setManualLoading("");
  };

  // Theme Colors
  const getRiskColor = (level: string) => {
    if (['SAFE', 'LOW'].includes(level)) return 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20';
    if (['SUSPICIOUS', 'MEDIUM'].includes(level)) return 'text-amber-400 bg-amber-400/10 border-amber-400/20';
    return 'text-rose-500 bg-rose-500/10 border-rose-500/20';
  };
  
  const getDecisionColor = (action: string, status: string) => {
    if (status.includes("APPROVED") || action === 'ALLOW') return 'text-emerald-400';
    if (status.includes("REJECTED") || ['BLOCK', 'BLOCK_MERCHANT'].includes(action)) return 'text-rose-500';
    return 'text-amber-400';
  };

  return (
    <div className="min-h-screen bg-[#0A0E17] text-slate-300 font-sans selection:bg-indigo-500/30">
      {/* HEADER */}
      <header className="border-b border-slate-800 bg-[#0F1420] sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-auto sm:h-16 flex flex-col sm:flex-row items-start sm:items-center justify-between py-3 sm:py-0">
          <div className="flex items-center space-x-3 mb-3 sm:mb-0">
            <div className="w-8 h-8 rounded bg-indigo-500 flex items-center justify-center font-bold text-white shadow-[0_0_15px_rgba(99,102,241,0.5)]">
              AI
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white leading-tight">Risk Manager <span className="text-indigo-400 font-medium hidden sm:inline">Enterprise</span></h1>
              <div className="text-[10px] text-slate-400 sm:hidden">Autonomous Transaction Risk Intelligence</div>
            </div>
          </div>
          
          <div className="flex flex-col sm:flex-row items-start sm:items-center space-y-3 sm:space-y-0 sm:space-x-6 w-full sm:w-auto">
            <div className="flex items-center space-x-2 text-sm font-medium">
              <span className="text-slate-400 hidden lg:inline">System Status:</span>
              {autoRunning ? (
                <span className="flex items-center text-emerald-400"><span className="w-2 h-2 rounded-full bg-emerald-400 mr-2 animate-pulse"></span>PROTECTION ACTIVE</span>
              ) : (
                <span className="flex items-center text-slate-500"><span className="w-2 h-2 rounded-full bg-slate-500 mr-2"></span>PROTECTION OFF</span>
              )}
            </div>
            <div className="hidden sm:block h-6 w-px bg-slate-700"></div>
            
            <nav className="flex space-x-1 overflow-x-auto w-full sm:w-auto pb-1 sm:pb-0 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              <button onClick={() => setActiveTab('dashboard')} className={`px-4 py-1.5 rounded-md text-sm font-semibold transition-all ${activeTab === 'dashboard' ? 'bg-slate-800 text-white shadow-sm' : 'text-slate-400 hover:text-white'}`}>AUTOMATED</button>
              <button onClick={() => setActiveTab('manual')} className={`px-4 py-1.5 rounded-md text-sm font-semibold transition-all ${activeTab === 'manual' ? 'bg-slate-800 text-white shadow-sm' : 'text-slate-400 hover:text-white'}`}>MANUAL</button>
              <button onClick={() => setActiveTab('model')} className={`px-4 py-1.5 rounded-md text-sm font-semibold transition-all ${activeTab === 'model' ? 'bg-slate-800 text-white shadow-sm' : 'text-slate-400 hover:text-white'}`}>MODEL EVAL</button>
              <button onClick={() => setActiveTab('impact')} className={`px-4 py-1.5 rounded-md text-sm font-semibold transition-all ${activeTab === 'impact' ? 'bg-slate-800 text-white shadow-sm' : 'text-slate-400 hover:text-white'}`}>BUSINESS IMPACT</button>
              <button onClick={() => setActiveTab('system')} className={`px-4 py-1.5 rounded-md text-sm font-semibold transition-all ${activeTab === 'system' ? 'bg-slate-800 text-white shadow-sm' : 'text-slate-400 hover:text-white'}`}>SYSTEM / AUDIT</button>
              
              <div className="h-6 w-px bg-slate-700 mx-2"></div>
              
              <button onClick={() => {
                setActiveTab('manual');
                setManualTx({
                    transaction_id: "DEMO-" + Math.floor(Math.random() * 1000000),
                    user_id: "USR-FRAUD-RING",
                    merchant_id: "MERCH-HIGH-RISK",
                    amount: 85000.0,
                    currency: "USD",
                    device_id: "DEV-NEW-HACKED",
                    location: "RU",
                    timestamp: new Date().toISOString()
                  });
              }} className="whitespace-nowrap px-4 py-1.5 rounded-md text-sm font-semibold transition-all bg-indigo-500/20 text-indigo-400 hover:bg-indigo-500 hover:text-white border border-indigo-500/30">JUDGE DEMO</button>
            </nav>

          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {activeTab === 'dashboard' && (
          <div className="space-y-8 animate-in fade-in duration-500">
            {/* METRICS ROW */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <MetricCard title="Total Analyzed" value={autoStats.total} />
              <MetricCard title="High Risk Blocked" value={autoStats.blocked} color="text-rose-500" />
              <MetricCard title="Safe Transactions" value={autoStats.allowed} color="text-emerald-400" />
              <MetricCard title="Pending Review" value={autoStats.pendingReview} color="text-amber-400" highlight={autoStats.pendingReview > 0} />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* LEFT COLUMN: CONTROL & FEED */}
              <div className="lg:col-span-2 flex flex-col space-y-6 h-full">
                
                {/* AUTOMATION CONTROL */}
                <div className="bg-[#131927] border border-slate-800 rounded-xl p-6 shadow-xl relative overflow-hidden">
                  <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-indigo-500 to-purple-500 opacity-50"></div>
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-lg font-bold text-white mb-1">Protection Engine</h2>
                      <p className="text-sm text-slate-400">Autonomous threat detection & response</p>
                    </div>
                    {autoRunning ? (
                      <button onClick={() => setAutoRunning(false)} className="px-6 py-2.5 rounded-lg font-bold text-white bg-rose-500 hover:bg-rose-600 transition-colors shadow-[0_0_20px_rgba(244,63,94,0.3)]">
                        STOP PROTECTION
                      </button>
                    ) : (
                      <button onClick={() => setAutoRunning(true)} className="px-6 py-2.5 rounded-lg font-bold text-white bg-indigo-500 hover:bg-indigo-600 transition-colors shadow-[0_0_20px_rgba(99,102,241,0.3)]">
                        START PROTECTION
                      </button>
                    )}
                  </div>
                </div>

                {/* LIVE FEED */}
                <div className="bg-[#131927] border border-slate-800 rounded-xl overflow-hidden shadow-xl flex flex-col flex-1 relative min-h-[400px]">
                  <div className="px-4 sm:px-6 py-4 border-b border-slate-800 flex flex-col sm:flex-row justify-between items-start sm:items-center bg-[#0F1420] space-y-3 sm:space-y-0 relative z-10">
                    <div className="flex items-center space-x-4 w-full sm:w-auto justify-between sm:justify-start">
                      <h2 className="text-lg font-bold text-white flex items-center">
                        Live Feed 
                        {autoRunning && <span className="ml-3 flex h-2.5 w-2.5 relative"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span><span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-indigo-500"></span></span>}
                      </h2>
                      <input 
                        type="text" 
                        placeholder="Search ID..." 
                        className="bg-[#1A2234] border border-slate-700 rounded px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500 w-32 sm:w-48 font-mono"
                        value={searchQuery}
                        onChange={e => setSearchQuery(e.target.value)}
                      />
                    </div>
                  </div>
                  <div className="flex-1 relative">
                    <div className="absolute inset-0 overflow-y-auto p-4 space-y-3 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
                    {feed.filter(item => item.tx.transaction_id.toLowerCase().includes(searchQuery.toLowerCase())).length === 0 ? (
                      <div className="h-full flex items-center justify-center flex-col text-slate-500 space-y-2">
                        {feed.length === 0 ? (
                          <>
                            <div className="w-12 h-12 rounded-full border-2 border-dashed border-slate-700 animate-[spin_4s_linear_infinite]"></div>
                            <p>Waiting for transaction stream...</p>
                          </>
                        ) : (
                          <p>No transactions found matching "{searchQuery}"</p>
                        )}
                      </div>
                    ) : (
                      feed.filter(item => item.tx.transaction_id.toLowerCase().includes(searchQuery.toLowerCase())).map((item, i) => (
                        <div key={i} className="bg-[#1A2234] border border-slate-700/50 rounded-lg p-4 transition-all hover:border-slate-600 group">
                          <div className="flex justify-between items-start mb-3">
                            <div className="flex items-center space-x-3">
                              <span className="font-mono text-white font-medium">{item.tx.transaction_id}</span>
                              <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-sm bg-slate-800 text-slate-400">DEMO / SIMULATED</span>
                            </div>
                            <span className="text-xs text-slate-500">{new Date(item.result.timestamp).toLocaleTimeString()}</span>
                          </div>
                          
                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 text-sm">
                            <div>
                              <div className="text-slate-500 text-[10px] sm:text-xs mb-1">Amount</div>
                              <div className="font-mono text-slate-200">${item.tx.amount.toLocaleString()}</div>
                            </div>
                            <div>
                              <div className="text-slate-500 text-[10px] sm:text-xs mb-1">Risk Score</div>
                              <div className="font-mono text-slate-200">{item.result.final_score}/100</div>
                            </div>
                            <div>
                              <div className="text-slate-500 text-xs mb-1">Level</div>
                              <div className={`inline-flex px-2 py-0.5 rounded text-xs font-bold uppercase ${getRiskColor(item.result.risk_level)}`}>
                                {item.result.risk_level}
                              </div>
                            </div>
                            <div>
                              <div className="text-slate-500 text-xs mb-1">Decision / Status</div>
                              <div className={`font-bold uppercase ${getDecisionColor(item.result.policy_action, item.status)}`}>
                                {item.status === 'PENDING' ? 'PENDING HUMAN REVIEW' : item.status === 'PROCESSED' ? item.result.policy_action : item.status}
                              </div>
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                    </div>
                  </div>
                </div>
              </div>

              {/* RIGHT COLUMN: APPROVAL QUEUE & SYSTEM TRACE */}
              <div className="lg:col-span-1 flex flex-col space-y-6 h-full">
                <div className="bg-[#131927] border border-slate-800 rounded-xl overflow-hidden shadow-xl flex flex-col h-[400px] lg:h-[450px]">
                  <div className="px-6 py-4 border-b border-rose-900/30 bg-rose-950/10 flex flex-col sm:flex-row justify-between items-start sm:items-center space-y-3 sm:space-y-0">
                    <div className="flex items-center space-x-3">
                      <h2 className="text-lg font-bold text-rose-400 flex items-center">
                        ⚠ Human Approval
                      </h2>
                      {pendingApprovals.length > 0 && (
                        <span className="bg-rose-500 text-white text-xs font-bold px-2 py-1 rounded-full">{pendingApprovals.length}</span>
                      )}
                    </div>
                    {pendingApprovals.length > 0 && (
                      <input 
                        type="text" 
                        placeholder="Search ID..." 
                        className="bg-[#1A2234] border border-rose-900/50 rounded px-2 py-1 text-xs text-white focus:outline-none focus:border-rose-500 w-full sm:w-32 font-mono"
                        value={searchQueue}
                        onChange={e => setSearchQueue(e.target.value)}
                      />
                    )}
                  </div>
                  
                  <div className="flex-1 overflow-y-auto p-4 space-y-4 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
                    {pendingApprovals.filter(i => i.tx.transaction_id.toLowerCase().includes(searchQueue.toLowerCase())).length === 0 ? (
                      <div className="text-center text-slate-500 py-10">
                        <p>{pendingApprovals.length === 0 ? "No transactions pending review." : "No matching transactions."}</p>
                      </div>
                    ) : (
                      pendingApprovals.filter(i => i.tx.transaction_id.toLowerCase().includes(searchQueue.toLowerCase())).map((item, i) => (
                        <div key={i} className="bg-[#1A2234] border border-rose-900/50 rounded-lg p-5 shadow-lg relative overflow-hidden animate-in slide-in-from-right-4">
                          <div className="absolute top-0 left-0 w-1 h-full bg-rose-500"></div>
                          <div className="flex justify-between items-start mb-4">
                            <span className="font-mono text-white font-bold">{item.tx.transaction_id}</span>
                            <span className="font-mono text-lg text-rose-400">${item.tx.amount.toLocaleString()}</span>
                          </div>
                          
                          <div className="mb-4">
                            <div className="flex justify-between text-xs mb-1">
                              <span className="text-slate-400">Risk Score</span>
                              <span className="text-rose-400 font-bold">{item.result.final_score}/100</span>
                            </div>
                            <div className="w-full bg-slate-800 rounded-full h-1.5">
                              <div className="bg-gradient-to-r from-amber-400 to-rose-500 h-1.5 rounded-full" style={{ width: `${item.result.final_score}%` }}></div>
                            </div>
                          </div>
                          
                          <div className="text-xs text-slate-400 mb-5 space-y-1">
                            <p className="font-semibold text-slate-300 mb-2">Risk Factors:</p>
                            {item.result.rule_signals.slice(0,3).map((sig, idx) => (
                              <div key={idx} className="flex items-start"><span className="text-rose-500 mr-2">•</span>{sig}</div>
                            ))}
                          </div>
                          
                          <div className="flex flex-col sm:flex-row space-y-2 sm:space-y-0 sm:space-x-3">
                            <button onClick={() => resolveTransaction(item.tx.transaction_id, "APPROVE")} className="flex-1 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 py-3 sm:py-2 rounded font-bold text-xs transition-colors flex justify-center items-center">
                              ✓ APPROVE
                            </button>
                            <button onClick={() => resolveTransaction(item.tx.transaction_id, "REJECT")} className="flex-1 bg-rose-500 hover:bg-rose-600 text-white py-3 sm:py-2 rounded font-bold text-xs transition-colors flex justify-center items-center shadow-lg shadow-rose-500/20">
                              ✕ REJECT
                            </button>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                {/* 2. APPROVED TRANSACTIONS */}
                {resolvedApprovals.filter(i => i.action === 'APPROVE').length > 0 && (
                  <div className="bg-[#131927] border border-slate-800 rounded-xl overflow-hidden shadow-xl flex flex-col max-h-[250px]">
                    <div className="px-6 py-3 border-b border-emerald-900/30 bg-emerald-950/10 flex flex-col sm:flex-row justify-between items-start sm:items-center space-y-2 sm:space-y-0">
                      <h2 className="text-sm font-bold text-emerald-400 flex items-center">
                        ✓ Approved Transactions
                      </h2>
                      <input 
                        type="text" 
                        placeholder="Search ID..." 
                        className="bg-[#1A2234] border border-emerald-900/50 rounded px-2 py-1 text-xs text-white focus:outline-none focus:border-emerald-500 w-full sm:w-28 font-mono"
                        value={searchApproved}
                        onChange={e => setSearchApproved(e.target.value)}
                      />
                    </div>
                    <div className="flex-1 overflow-y-auto p-4 space-y-3 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
                      {resolvedApprovals.filter(i => i.action === 'APPROVE' && i.tx.transaction_id.toLowerCase().includes(searchApproved.toLowerCase())).map((item, i) => (
                        <div key={i} className="bg-[#1A2234] border border-emerald-900/50 rounded-lg p-3 shadow relative overflow-hidden">
                          <div className="absolute top-0 left-0 w-1 h-full bg-emerald-500"></div>
                          <div className="flex justify-between items-center">
                            <span className="font-mono text-slate-300 text-xs">{item.tx.transaction_id}</span>
                            <span className="font-mono text-xs text-emerald-400">${item.tx.amount.toLocaleString()}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 3. REJECTED TRANSACTIONS */}
                {resolvedApprovals.filter(i => i.action === 'REJECT').length > 0 && (
                  <div className="bg-[#131927] border border-slate-800 rounded-xl overflow-hidden shadow-xl flex flex-col max-h-[250px]">
                    <div className="px-6 py-3 border-b border-rose-900/30 bg-rose-950/10 flex flex-col sm:flex-row justify-between items-start sm:items-center space-y-2 sm:space-y-0">
                      <h2 className="text-sm font-bold text-rose-400 flex items-center">
                        ✕ Rejected Transactions
                      </h2>
                      <input 
                        type="text" 
                        placeholder="Search ID..." 
                        className="bg-[#1A2234] border border-rose-900/50 rounded px-2 py-1 text-xs text-white focus:outline-none focus:border-rose-500 w-full sm:w-28 font-mono"
                        value={searchRejected}
                        onChange={e => setSearchRejected(e.target.value)}
                      />
                    </div>
                    <div className="flex-1 overflow-y-auto p-4 space-y-3 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
                      {resolvedApprovals.filter(i => i.action === 'REJECT' && i.tx.transaction_id.toLowerCase().includes(searchRejected.toLowerCase())).map((item, i) => (
                        <div key={i} className="bg-[#1A2234] border border-rose-900/50 rounded-lg p-3 shadow relative overflow-hidden">
                          <div className="absolute top-0 left-0 w-1 h-full bg-rose-500"></div>
                          <div className="flex justify-between items-center mb-2">
                            <span className="font-mono text-slate-300 text-xs">{item.tx.transaction_id}</span>
                            <span className="font-mono text-xs text-rose-400">${item.tx.amount.toLocaleString()}</span>
                          </div>
                          <div className="flex space-x-2">
                            <button onClick={() => resolveTransaction(item.tx.transaction_id, "APPROVE")} className="flex-1 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 py-1.5 rounded font-bold text-[10px] transition-colors">
                              REVERT TO APPROVE
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 4. ALL RESOLVED TRANSACTIONS */}
                {resolvedApprovals.length > 0 && (
                  <div className="bg-[#131927] border border-slate-800 rounded-xl overflow-hidden shadow-xl flex flex-col max-h-[300px]">
                    <div className="px-6 py-3 border-b border-indigo-900/30 bg-indigo-950/10 flex flex-col sm:flex-row justify-between items-start sm:items-center space-y-2 sm:space-y-0">
                      <h2 className="text-sm font-bold text-indigo-400 flex items-center">
                        All Resolved Transactions
                      </h2>
                      <input 
                        type="text" 
                        placeholder="Search ID..." 
                        className="bg-[#1A2234] border border-indigo-900/50 rounded px-2 py-1 text-xs text-white focus:outline-none focus:border-indigo-500 w-full sm:w-28 font-mono"
                        value={searchResolved}
                        onChange={e => setSearchResolved(e.target.value)}
                      />
                    </div>
                    
                    <div className="flex-1 overflow-y-auto p-4 space-y-3 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
                      {resolvedApprovals.filter(i => i.tx.transaction_id.toLowerCase().includes(searchResolved.toLowerCase())).map((item, i) => (
                        <div key={i} className="bg-[#1A2234] border border-slate-800 rounded-lg p-3 shadow relative overflow-hidden flex justify-between items-center">
                          <div className={`absolute top-0 left-0 w-1 h-full ${item.action === 'APPROVE' ? 'bg-emerald-500' : 'bg-rose-500'}`}></div>
                          <div className="flex items-center space-x-3">
                             <span className="font-mono text-slate-300 text-[10px]">{item.tx.transaction_id}</span>
                             <span className={`text-[10px] font-bold uppercase ${item.action === 'APPROVE' ? 'text-emerald-500' : 'text-rose-500'}`}>{item.action}</span>
                          </div>
                          <span className={`font-mono text-[10px] ${item.action === 'APPROVE' ? 'text-emerald-400' : 'text-rose-400'}`}>${item.tx.amount.toLocaleString()}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* SYSTEM HEALTH & CONTROLS */}
                <div className="bg-[#131927] border border-slate-800 rounded-xl p-5 shadow-xl">
                  <h2 className="text-sm font-bold mb-3 text-cyan-400 uppercase tracking-wider">System Health & Controls</h2>
                  {systemState ? (
                    <div className="space-y-2 text-xs font-mono">
                      <div className="flex justify-between">
                        <span className="text-slate-400">System Mode:</span> 
                        <span className={systemState.system_state === 'NORMAL' ? 'text-emerald-400 font-bold' : 'text-rose-500 font-bold animate-pulse'}>{systemState.system_state}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Redis Broker:</span> 
                        <span className="text-emerald-400">{systemState.redis_status}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Event Bus:</span> 
                        <span className="text-emerald-400">{systemState.event_bus_status}</span>
                      </div>
                      
                      <div className="mt-4 pt-3 border-t border-slate-800">
                        <button 
                          onClick={() => toggleKillSwitch(systemState.system_state === 'NORMAL')}
                          className={`w-full py-2 rounded font-bold transition-colors ${systemState.system_state === 'NORMAL' ? 'bg-rose-500/10 text-rose-500 border border-rose-500/30 hover:bg-rose-500/20' : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/20'}`}
                        >
                          {systemState.system_state === 'NORMAL' ? 'ACTIVATE KILL SWITCH' : 'DEACTIVATE KILL SWITCH'}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="text-slate-500 text-xs">Loading system state...</div>
                  )}
                </div>

                {/* SYSTEM TRACE (AUDIT) */}
                <div className="bg-[#131927] border border-slate-800 rounded-xl p-5 shadow-xl flex flex-col h-[300px]">
                  <h2 className="text-sm font-bold mb-3 text-emerald-400 uppercase tracking-wider">System Trace (Audit)</h2>
                  <div className="overflow-y-auto flex-1 space-y-2 font-mono text-[10px] [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
                    {systemState?.recent_events?.length > 0 ? (
                      [...systemState.recent_events].map((ev: any, i: number) => (
                        <div key={i} className="border-l-2 border-emerald-500/50 pl-2 py-1 bg-[#1A2234] rounded">
                          <div className="text-emerald-400 font-bold">{ev.event_type}</div>
                          <div className="text-slate-500 truncate">ID: {ev.correlation_id}</div>
                          <div className="text-slate-400 mt-0.5 truncate">{JSON.stringify(ev.payload).substring(0, 80)}...</div>
                        </div>
                      ))
                    ) : (
                      <div className="text-slate-500 italic">No recent events.</div>
                    )}
                  </div>
                </div>
                
                {/* FRAUD SPIKE DETECTOR */}
                <div className="bg-[#131927] border border-slate-800 rounded-xl p-5 shadow-xl flex flex-col">
                  <h2 className="text-sm font-bold mb-3 text-rose-400 uppercase tracking-wider flex justify-between">
                    <span>Fraud Spike Detector</span>
                    <span className="text-xs bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded">SIMULATED</span>
                  </h2>
                  <div className="space-y-3 text-sm">
                    <div className="flex justify-between text-slate-400 border-b border-slate-800 pb-2">
                      <span>Baseline Risk Rate</span>
                      <span className="font-mono">2.4%</span>
                    </div>
                    <div className="flex justify-between items-center text-slate-300">
                      <span>Current Risk Rate</span>
                      <span className={`font-mono text-xl font-bold ${autoStats.high > 5 ? 'text-rose-500' : 'text-emerald-400'}`}>
                        {autoStats.analyzed > 0 ? ((autoStats.high / autoStats.analyzed) * 100).toFixed(1) + '%' : '0.0%'}
                      </span>
                    </div>
                    {autoStats.analyzed > 0 && ((autoStats.high / autoStats.analyzed) * 100) > 10.0 ? (
                       <div className="mt-3 p-3 bg-rose-500/10 border border-rose-500/30 rounded text-rose-400 text-xs">
                          <strong className="block mb-1">⚠ FRAUD SPIKE DETECTED</strong>
                          Elevated risk volume detected. Suggest routing more transactions to review.
                       </div>
                    ) : (
                       <div className="mt-3 p-3 bg-emerald-500/10 border border-emerald-500/30 rounded text-emerald-400 text-xs">
                          ● Normal Traffic Patterns
                       </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* MANUAL TAB */}
        {activeTab === 'manual' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 animate-in fade-in duration-500">
            <div className="bg-[#131927] border border-slate-800 rounded-xl p-8 shadow-xl">
              <h2 className="text-xl font-bold mb-6 text-white border-b border-slate-800 pb-4">Manual Transaction Analysis</h2>
              
              <div className="flex space-x-2 mb-8">
                <button onClick={() => {
                  const amounts = [20, 50, 150, 300, 1500, 8000, 32000, 85000];
                  const locations = ["US", "US", "US", "UK", "IN", "CN", "RU", "KP"];
                  const devices = ["DEV-OLD", "DEV-NEW", "DEV-NEW-HACKED"];
                  setManualTx({
                    transaction_id: "TXN-" + Math.floor(Math.random() * 1000000),
                    user_id: "USR-" + Math.floor(Math.random() * 1000),
                    merchant_id: "MERCH-" + Math.floor(Math.random() * 500),
                    amount: amounts[Math.floor(Math.random() * amounts.length)],
                    currency: "USD",
                    device_id: devices[Math.floor(Math.random() * devices.length)],
                    location: locations[Math.floor(Math.random() * locations.length)],
                    timestamp: new Date().toISOString()
                  });
                }} className="w-full text-xs px-4 py-3 bg-slate-800 text-white rounded-lg hover:bg-slate-700 border border-slate-600 font-bold tracking-wider flex items-center justify-center transition-colors">
                  <svg className="w-4 h-4 mr-2 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
                  GENERATE RANDOM TRANSACTION
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
                {Object.keys(manualTx).map(k => (
                  <div key={k} className={k === 'timestamp' || k === 'transaction_id' ? 'col-span-1 sm:col-span-2' : 'col-span-1'}>
                    <label className="block text-slate-500 text-xs font-bold uppercase tracking-wider mb-1.5">{k.replace('_', ' ')}</label>
                    <input 
                      className="w-full bg-[#0A0E17] border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                      value={(manualTx as any)[k]} 
                      onChange={e => setManualTx({...manualTx, [k]: e.target.value})} 
                    />
                  </div>
                ))}
              </div>
              
              <button onClick={runManualAnalysis} disabled={!!manualLoading} className="w-full py-3.5 rounded-lg bg-indigo-500 hover:bg-indigo-600 text-white font-bold shadow-[0_0_20px_rgba(99,102,241,0.3)] transition-all disabled:opacity-50 flex justify-center items-center">
                {manualLoading ? <span className="animate-spin w-5 h-5 border-2 border-white/30 border-t-white rounded-full"></span> : "ANALYZE TRANSACTION"}
              </button>
            </div>

            <div className="bg-[#131927] border border-slate-800 rounded-xl p-8 shadow-xl">
              <h2 className="text-xl font-bold mb-6 text-white border-b border-slate-800 pb-4">Analysis Results</h2>
              {manualError && <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-lg text-rose-400 text-sm mb-6">{manualError}</div>}
              
              {!manualResult && !manualLoading && !manualError && (
                <div className="h-64 flex items-center justify-center text-slate-500 flex-col">
                  Submit a transaction to view comprehensive risk breakdown.
                </div>
              )}

              {manualResult && (
                <div className="space-y-8 animate-in slide-in-from-bottom-4">
                  <div>
                    <div className="flex justify-between items-end mb-2">
                      <span className="text-slate-400 font-medium">Composite Risk Score</span>
                      <span className="text-3xl font-mono text-white">{manualResult.final_score}<span className="text-slate-500 text-xl">/100</span></span>
                    </div>
                    <div className="w-full bg-slate-800 rounded-full h-2">
                      <div className={`h-2 rounded-full ${manualResult.final_score < 40 ? 'bg-emerald-400' : manualResult.final_score < 75 ? 'bg-amber-400' : 'bg-rose-500'}`} style={{ width: `${manualResult.final_score}%` }}></div>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-4 bg-[#0A0E17] border border-slate-800 rounded-lg">
                      <div className="text-xs text-slate-500 uppercase font-bold mb-1">Risk Level</div>
                      <div className={`font-bold ${getRiskColor(manualResult.risk_level).split(' ')[0]}`}>{manualResult.risk_level}</div>
                    </div>
                    <div className="p-4 bg-[#0A0E17] border border-slate-800 rounded-lg">
                      <div className="text-xs text-slate-500 uppercase font-bold mb-1">Policy Action</div>
                      <div className={`font-bold ${getDecisionColor(manualResult.policy_action, "")}`}>{manualResult.policy_action}</div>
                    </div>
                  </div>

                  <div>
                    <h3 className="text-sm font-bold text-white uppercase mb-3 pb-2 border-b border-slate-800">Risk Signals</h3>
                    {manualResult.rule_signals.length > 0 ? (
                      <ul className="space-y-2">
                        {manualResult.rule_signals.map((s: string, i: number) => (
                          <li key={i} className="flex items-start text-sm text-slate-300">
                            <span className="text-amber-500 mr-2 mt-0.5">⚠</span>{s}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-slate-500 text-sm">No abnormal signals detected.</p>
                    )}
                  </div>
                  
                  <div className="p-4 bg-indigo-500/10 border border-indigo-500/20 rounded-lg text-indigo-200 text-sm">
                    <strong>Explanation:</strong> {manualResult.explanation}
                  </div>
                  
                  <div className="flex flex-col sm:flex-row space-y-3 sm:space-y-0 sm:space-x-3 pt-6 mt-6 border-t border-slate-800">
                    <button onClick={() => handleManualResolution("APPROVE")} className="flex-1 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 py-3 rounded-lg font-bold text-sm transition-colors flex justify-center items-center">
                      ✓ APPROVE & VIEW
                    </button>
                    <button onClick={() => handleManualResolution("REJECT")} className="flex-1 bg-rose-500 hover:bg-rose-600 text-white py-3 rounded-lg font-bold text-sm transition-colors flex justify-center items-center shadow-lg shadow-rose-500/20">
                      ✕ REJECT & VIEW
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      
        {activeTab === 'model' && (
          <div className="space-y-8 animate-in fade-in duration-500">
            <h2 className="text-2xl font-bold text-white mb-2">Model Evaluation Center</h2>
            <p className="text-slate-400 mb-8">Performance metrics computed against held-out testing dataset.</p>
            
            {mlMetrics ? (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                  <MetricCard title="Test Samples" value={mlMetrics.test_samples} />
                  <MetricCard title="Precision" value={(mlMetrics.precision * 100).toFixed(1) + '%'} color="text-indigo-400" />
                  <MetricCard title="Recall" value={(mlMetrics.recall * 100).toFixed(1) + '%'} color="text-indigo-400" />
                  <MetricCard title="F1 Score" value={(mlMetrics.f1_score * 100).toFixed(1) + '%'} color="text-emerald-400" />
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                  <div className="bg-[#131927] border border-slate-800 rounded-xl p-4 sm:p-6 shadow-xl overflow-x-auto">
                    <h3 className="text-lg font-bold text-white mb-4">Confusion Matrix (Held-out Set)</h3>
                    <div className="grid grid-cols-3 gap-2 text-center text-xs sm:text-sm font-mono min-w-[300px]">
                      <div></div>
                      <div className="text-slate-400 pb-2">PREDICTED FRAUD</div>
                      <div className="text-slate-400 pb-2">PREDICTED SAFE</div>
                      
                      <div className="text-slate-400 flex items-center justify-end pr-4">ACTUAL FRAUD</div>
                      <div className="bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 p-4 rounded-lg">
                        <div className="text-2xl font-bold">{mlMetrics.true_positives}</div>
                        <div className="text-[10px] uppercase">True Positive (Blocked)</div>
                      </div>
                      <div className="bg-rose-500/10 border border-rose-500/30 text-rose-400 p-4 rounded-lg">
                        <div className="text-2xl font-bold">{mlMetrics.false_negatives}</div>
                        <div className="text-[10px] uppercase">False Negative (Missed)</div>
                      </div>
                      
                      <div className="text-slate-400 flex items-center justify-end pr-4">ACTUAL SAFE</div>
                      <div className="bg-amber-500/10 border border-amber-500/30 text-amber-400 p-4 rounded-lg">
                        <div className="text-2xl font-bold">{mlMetrics.false_positives}</div>
                        <div className="text-[10px] uppercase">False Positive (Friction)</div>
                      </div>
                      <div className="bg-slate-800/50 border border-slate-700 text-slate-300 p-4 rounded-lg">
                        <div className="text-2xl font-bold">{mlMetrics.true_negatives}</div>
                        <div className="text-[10px] uppercase">True Negative (Allowed)</div>
                      </div>
                    </div>
                  </div>
                  
                  <div className="bg-[#131927] border border-slate-800 rounded-xl p-6 shadow-xl flex flex-col justify-center">
                    <h3 className="text-lg font-bold text-white mb-4">Metrics Explanation</h3>
                    <div className="space-y-4 text-sm text-slate-300">
                      <div>
                        <strong className="text-indigo-400 block mb-1">Precision ({(mlMetrics.precision * 100).toFixed(1)}%)</strong>
                        Of the transactions the model flagged as risky, how many were actually fraudulent? High precision means fewer false positives.
                      </div>
                      <div>
                        <strong className="text-indigo-400 block mb-1">Recall ({(mlMetrics.recall * 100).toFixed(1)}%)</strong>
                        Of all truly fraudulent transactions, how many did the system successfully catch? High recall means fewer missed frauds.
                      </div>
                      <div>
                        <strong className="text-emerald-400 block mb-1">F1 Score ({(mlMetrics.f1_score * 100).toFixed(1)}%)</strong>
                        Harmonic mean of Precision and Recall. Represents the balanced performance of the model.
                      </div>
                    </div>
                  </div>
                </div>
              </>
            ) : systemError ? (
              <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-lg text-rose-400 text-sm">{systemError}</div>
            ) : (
              <div className="text-slate-500">Loading metrics...</div>
            )}
          </div>
        )}

        {activeTab === 'impact' && (
          <div className="space-y-8 animate-in fade-in duration-500">
            <h2 className="text-2xl font-bold text-white mb-2">Business Impact Simulator</h2>
            <p className="text-slate-400 mb-8 flex items-center">
              <span className="bg-indigo-500/20 text-indigo-400 px-2 py-0.5 rounded text-xs font-bold mr-3 border border-indigo-500/30">SIMULATED DATA</span>
              Estimated financial impact of the AI Risk Manager on current transaction volume.
            </p>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="bg-[#131927] border border-slate-800 rounded-xl p-6 shadow-xl relative overflow-hidden">
                <div className="absolute top-0 left-0 w-1 h-full bg-emerald-500"></div>
                <h3 className="text-lg font-bold text-white mb-4">Loss Prevention</h3>
                <div className="space-y-4">
                  <div className="flex justify-between items-center pb-4 border-b border-slate-800">
                    <span className="text-slate-400">Total Analyzed Volume</span>
                    <span className="font-mono text-white">${(autoStats.analyzed * 1500).toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between items-center pb-4 border-b border-slate-800">
                    <span className="text-slate-400">High Risk Blocked (Estimated)</span>
                    <span className="font-mono text-rose-400">${(autoStats.blocked * 1250).toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between items-center pt-2">
                    <span className="text-white font-bold">Estimated Fraud Prevented</span>
                    <span className="font-mono text-emerald-400 text-xl font-bold">${(autoStats.blocked * 1250 * 0.9).toLocaleString()}</span>
                  </div>
                </div>
              </div>

              <div className="bg-[#131927] border border-slate-800 rounded-xl p-6 shadow-xl relative overflow-hidden">
                <div className="absolute top-0 left-0 w-1 h-full bg-amber-500"></div>
                <h3 className="text-lg font-bold text-white mb-4">False Positive Cost</h3>
                <div className="space-y-4">
                  <div className="flex justify-between items-center pb-4 border-b border-slate-800">
                    <span className="text-slate-400">Manual Reviews Triggered</span>
                    <span className="font-mono text-white">{autoStats.pendingReview + resolvedApprovals.length}</span>
                  </div>
                  <div className="flex justify-between items-center pb-4 border-b border-slate-800">
                    <span className="text-slate-400">Est. Review Cost ($15/review)</span>
                    <span className="font-mono text-amber-400">${((autoStats.pendingReview + resolvedApprovals.length) * 15).toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between items-center pt-2">
                    <span className="text-white font-bold">Net Operational Saving</span>
                    <span className="font-mono text-emerald-400 text-xl font-bold">
                      ${((autoStats.blocked * 1250 * 0.9) - ((autoStats.pendingReview + resolvedApprovals.length) * 15)).toLocaleString()}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'system' && (
          <div className="space-y-8 animate-in fade-in duration-500">
            <h2 className="text-2xl font-bold text-white mb-6">System Health & Audit</h2>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              <div className="lg:col-span-1 space-y-6">
                <div className="bg-[#131927] border border-slate-800 rounded-xl p-6 shadow-xl">
                  <h3 className="text-lg font-bold text-white mb-4">Infrastructure</h3>
                  {systemState ? (
                    <div className="space-y-4 font-mono text-sm">
                      <div className="flex justify-between items-center p-3 bg-slate-800/30 rounded border border-slate-700/50">
                        <span className="text-slate-400">Risk Engine</span>
                        <span className="text-emerald-400 flex items-center"><span className="w-2 h-2 rounded-full bg-emerald-400 mr-2"></span>ONLINE</span>
                      </div>
                      <div className="flex justify-between items-center p-3 bg-slate-800/30 rounded border border-slate-700/50">
                        <span className="text-slate-400">Event Bus (Redis)</span>
                        <span className={systemState.redis_status === 'CONNECTED' ? 'text-emerald-400 flex items-center' : 'text-rose-500 flex items-center'}>
                          <span className={`w-2 h-2 rounded-full ${systemState.redis_status === 'CONNECTED' ? 'bg-emerald-400' : 'bg-rose-500'} mr-2`}></span>
                          {systemState.redis_status}
                        </span>
                      </div>
                      <div className="flex justify-between items-center p-3 bg-slate-800/30 rounded border border-slate-700/50">
                        <span className="text-slate-400">System Mode</span>
                        <span className={systemState.system_state === 'NORMAL' ? 'text-emerald-400 flex items-center' : 'text-rose-500 flex items-center'}>
                          <span className={`w-2 h-2 rounded-full ${systemState.system_state === 'NORMAL' ? 'bg-emerald-400' : 'bg-rose-500 animate-ping'} mr-2`}></span>
                          {systemState.system_state}
                        </span>
                      </div>
                      <button 
                        onClick={() => toggleKillSwitch(systemState.system_state === 'NORMAL')}
                        className={`w-full py-3 mt-4 rounded-lg font-bold transition-all shadow-lg ${systemState.system_state === 'NORMAL' ? 'bg-rose-500 hover:bg-rose-600 text-white shadow-rose-500/20' : 'bg-emerald-500 hover:bg-emerald-600 text-white shadow-emerald-500/20'}`}
                      >
                        {systemState.system_state === 'NORMAL' ? 'EMERGENCY KILL SWITCH' : 'RESTORE NORMAL OPERATIONS'}
                      </button>
                    </div>
                  ) : systemError ? (
                    <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-lg text-rose-400 text-sm">{systemError}</div>
                  ) : (
                    <div className="text-slate-500">Loading system state...</div>
                  )}
                </div>
              </div>
              
              <div className="lg:col-span-2">
                <div className="bg-[#131927] border border-slate-800 rounded-xl p-6 shadow-xl h-full flex flex-col">
                  <h3 className="text-lg font-bold text-white mb-4">Enterprise Event Trace</h3>
                  <div className="flex-1 overflow-y-auto space-y-3 font-mono text-xs [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
                    {systemState?.recent_events?.length > 0 ? (
                      [...systemState.recent_events].reverse().map((ev: any, i: number) => (
                        <div key={i} className="bg-[#1A2234] border-l-4 border-indigo-500 rounded p-4 flex flex-col">
                          <div className="flex justify-between mb-2">
                            <span className="text-indigo-400 font-bold">{ev.event_type}</span>
                            <span className="text-slate-500">{new Date(ev.timestamp || Date.now()).toLocaleTimeString()}</span>
                          </div>
                          <span className="text-slate-400 mb-2 truncate">Trace ID: {ev.correlation_id}</span>
                          <pre className="text-slate-300 bg-[#0A0E17] p-2 rounded overflow-x-auto border border-slate-800 whitespace-pre-wrap break-words text-[10px]">
                            {JSON.stringify(ev.payload, null, 2)}
                          </pre>
                        </div>
                      ))
                    ) : (
                      <div className="text-slate-500 italic">No events recorded yet.</div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

      </main>
    </div>
  );
}

const MetricCard = ({ title, value, color = "text-white", highlight = false }: { title: string, value: number | string, color?: string, highlight?: boolean }) => (
  <div className={`bg-[#131927] border ${highlight ? 'border-amber-500/50 shadow-[0_0_15px_rgba(245,158,11,0.2)]' : 'border-slate-800'} p-5 rounded-xl`}>
    <h3 className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-2">{title}</h3>
    <p className={`text-3xl font-mono ${color}`}>{value}</p>
  </div>
);


