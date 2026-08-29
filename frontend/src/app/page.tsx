"use client";
import React, { useState, useEffect } from "react";

export default function Dashboard() {
  const [tx, setTx] = useState({
    transaction_id: "TXN-" + Math.floor(Math.random() * 10000),
    user_id: "USR-123",
    merchant_id: "MERCH-456",
    amount: 50.0,
    currency: "USD",
    device_id: "DEV-OLD",
    location: "US",
    timestamp: new Date().toISOString()
  });

  const [result, setResult] = useState<any>(null);
  const [systemState, setSystemState] = useState<any>(null);
  const [loadingState, setLoadingState] = useState("");
  const [error, setError] = useState("");
  const [scenarioDesc, setScenarioDesc] = useState("Select a scenario to populate transaction data.");
  const [activeTab, setActiveTab] = useState("manual"); // manual | integration

  const [autoRunning, setAutoRunning] = useState(false);
  const [autoStats, setAutoStats] = useState({
    total: 0, analyzed: 0, low: 0, medium: 0, high: 0, allowed: 0, flagged: 0, blocked: 0
  });
  const [autoTransactions, setAutoTransactions] = useState<any[]>([]);

  useEffect(() => {
    let interval: any;
    if (autoRunning) {
      interval = setInterval(async () => {
        const amounts = [20, 50, 250, 500, 1500, 8000, 50000];
        const locations = ["US", "US", "UK", "IN", "CN", "RU", "KP"];
        const devices = ["DEV-OLD", "DEV-NEW", "DEV-NEW-HACKED"];
        
        const simTx = {
          transaction_id: "TXN-" + Math.floor(Math.random() * 100000),
          user_id: "USR-" + Math.floor(Math.random() * 1000),
          merchant_id: "MERCH-" + Math.floor(Math.random() * 500),
          amount: amounts[Math.floor(Math.random() * amounts.length)],
          currency: "USD",
          device_id: devices[Math.floor(Math.random() * devices.length)],
          location: locations[Math.floor(Math.random() * locations.length)],
          timestamp: new Date().toISOString()
        };

        try {
          const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
          const res = await fetch(`${apiUrl}/api/v1/evaluate`, {
            method: "POST",
            headers: { 
              "Content-Type": "application/json",
              "X-API-Key": process.env.NEXT_PUBLIC_API_KEY || process.env.NEXT_PUBLIC_ADMIN_API_KEY || ""
            },
            body: JSON.stringify(simTx)
          });
          
          if (res.ok) {
            const result = await res.json();
            
            setAutoStats(prev => ({
              ...prev,
              total: prev.total + 1,
              analyzed: prev.analyzed + 1,
              low: ['SAFE', 'LOW'].includes(result.risk_level) ? prev.low + 1 : prev.low,
              medium: ['SUSPICIOUS', 'MEDIUM'].includes(result.risk_level) ? prev.medium + 1 : prev.medium,
              high: ['HIGH_RISK', 'CRITICAL', 'HIGH'].includes(result.risk_level) ? prev.high + 1 : prev.high,
              allowed: result.policy_action === 'ALLOW' ? prev.allowed + 1 : prev.allowed,
              flagged: ['FLAG', 'REQUIRE_APPROVAL', 'MANUAL_REVIEW'].includes(result.policy_action) ? prev.flagged + 1 : prev.flagged,
              blocked: ['BLOCK', 'BLOCK_MERCHANT', 'KILL_SWITCH'].includes(result.policy_action) ? prev.blocked + 1 : prev.blocked
            }));

            setAutoTransactions(prev => [
              { tx: simTx, result },
              ...prev
            ].slice(0, 10));
          }
        } catch (e) {
          console.error("Auto tx failed", e);
        }
      }, 3000);
    }
    return () => clearInterval(interval);
  }, [autoRunning]);


  const fetchSystemState = async () => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/v1/system/trace`, {
        headers: {
          "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbi11c2VyIiwicm9sZSI6IkFETUlOIiwiZXhwIjoxODkxMzY1NDM1fQ.qIAQJ2jptzbmkAJCpHeGp5s-rsJhhz6qjDUCkEpaSqc",
          "X-API-Key": process.env.NEXT_PUBLIC_API_KEY || process.env.NEXT_PUBLIC_ADMIN_API_KEY || ""
        }
      });
      if (res.ok) setSystemState(await res.json());
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchSystemState();
    const interval = setInterval(fetchSystemState, 3000);
    return () => clearInterval(interval);
  }, []);

  const analyze = async () => {
    setLoadingState("ANALYZING TRANSACTION...");
    setError("");
    setResult(null);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/v1/evaluate`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "X-API-Key": process.env.NEXT_PUBLIC_API_KEY || process.env.NEXT_PUBLIC_ADMIN_API_KEY || ""
        },
        body: JSON.stringify(tx)
      });
      if (!res.ok) {
        if (res.status === 401 || res.status === 403) setError("Administrative authorization required.");
        else if (res.status === 503) setError("Risk evaluation service temporarily unavailable. No transaction was executed.");
        else setError(`Request failed with status ${res.status}`);
      } else {
        const data = await res.json();
        setResult(data);
        if (data.execution_status === 'IDEMPOTENT_DUPLICATE') {
          setError("This transaction has already been processed. Duplicate execution was prevented.");
        } else if (data.authorization_state === 'PENDING_APPROVAL' && data.execution_status === 'KILL_SWITCH_ACTIVE') {
          setError("Autonomous actions are currently disabled by the administrator.");
        }
      }
      fetchSystemState();
    } catch (e) {
      console.error(e);
      setError("Network error. Risk evaluation service temporarily unavailable.");
    }
    setLoadingState("");
  };

  const setScenario = (type: string) => {
    const baseTx = { ...tx, transaction_id: "TXN-" + Math.floor(Math.random() * 10000), timestamp: new Date().toISOString() };
    if (type === "SAFE") {
      setTx({ ...baseTx, amount: 20, location: "US", device_id: "DEV-OLD", user_id: "USR-1" });
      setScenarioDesc("Normal transaction — trusted device, normal amount, normal location.");
    } else if (type === "SUSPICIOUS") {
      setTx({ ...baseTx, amount: 2500, location: "RU", device_id: "DEV-NEW", user_id: "USR-1" });
      setScenarioDesc("New device + unusual transaction pattern.");
    } else if (type === "HIGH_RISK") {
      setTx({ ...baseTx, amount: 8000, location: "KP", device_id: "DEV-NEW", user_id: "USR-2" });
      setScenarioDesc("High-risk transaction requiring human approval.");
    } else if (type === "CRITICAL") {
      setTx({ ...baseTx, amount: 50000, location: "KP", device_id: "DEV-NEW-HACKED", user_id: "USR-99" });
      setScenarioDesc("Critical transaction blocked by policy.");
    }
  };

  const toggleKillSwitch = async (active: boolean) => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    await fetch(`${apiUrl}/api/v1/system/kill-switch`, {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbi11c2VyIiwicm9sZSI6IkFETUlOIiwiZXhwIjoxODkxMzY1NDM1fQ.qIAQJ2jptzbmkAJCpHeGp5s-rsJhhz6qjDUCkEpaSqc",
        "X-API-Key": process.env.NEXT_PUBLIC_API_KEY || process.env.NEXT_PUBLIC_ADMIN_API_KEY || ""
      },
      body: JSON.stringify({ active })
    });
    fetchSystemState();
  };

  const toggleAutomatedProtection = async (active: boolean) => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    await fetch(`${apiUrl}/api/v1/integration/automation-state`, {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbi11c2VyIiwicm9sZSI6IkFETUlOIiwiZXhwIjoxODkxMzY1NDM1fQ.qIAQJ2jptzbmkAJCpHeGp5s-rsJhhz6qjDUCkEpaSqc",
        "X-API-Key": process.env.NEXT_PUBLIC_API_KEY || process.env.NEXT_PUBLIC_ADMIN_API_KEY || ""
      },
      body: JSON.stringify({ active })
    });
    fetchSystemState();
  };

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-6 font-sans">
      <div className="max-w-7xl mx-auto">
        <div className="flex space-x-4 mb-6 border-b border-gray-700 pb-2">
          <button 
            className={`font-bold px-4 py-2 ${activeTab === 'manual' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-500 hover:text-gray-300'}`}
            onClick={() => setActiveTab('manual')}
          >
            Manual Analysis
          </button>
          <button 
            className={`font-bold px-4 py-2 ${activeTab === 'integration' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-500 hover:text-gray-300'}`}
            onClick={() => setActiveTab('integration')}
          >
            Integration & Automated Protection
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* Left Column */}
          <div className="lg:col-span-1 space-y-6">
            {activeTab === 'manual' ? (
              <div className="bg-gray-800 p-6 rounded-lg border border-gray-700 shadow-xl">
                <h2 className="text-xl font-bold mb-4 text-blue-400">TRANSACTION ANALYZER</h2>
                
                <div className="text-xs font-bold text-gray-500 mb-2 uppercase">Test Transactions</div>
                <div className="flex flex-wrap gap-2 mb-4">
                  <button onClick={() => setScenario('SAFE')} className="text-xs px-2 py-1 bg-gray-700 text-gray-300 rounded hover:bg-gray-600">Generate Normal Transaction</button>
                  <button onClick={() => setScenario('SUSPICIOUS')} className="text-xs px-2 py-1 bg-gray-700 text-gray-300 rounded hover:bg-gray-600">Generate Suspicious Transaction</button>
                  <button onClick={() => setScenario('HIGH_RISK')} className="text-xs px-2 py-1 bg-gray-700 text-gray-300 rounded hover:bg-gray-600">Generate High-Risk Transaction</button>
                  <button onClick={() => setScenario('CRITICAL')} className="text-xs px-2 py-1 bg-gray-700 text-gray-300 rounded hover:bg-gray-600">Generate Critical Transaction</button>
                </div>
                
                <div className="mb-6 text-sm text-gray-400 italic border-l-4 border-blue-500 pl-3">
                  {scenarioDesc}
                </div>

                <div className="space-y-3 text-sm">
                  {Object.keys(tx).map(k => (
                    <div key={k}>
                      <label className="block text-gray-400 text-xs uppercase">{k}</label>
                      <input 
                        className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 mt-1 focus:outline-none focus:border-blue-500 text-gray-100"
                        value={(tx as any)[k]} 
                        onChange={e => setTx({...tx, [k]: e.target.value})} 
                      />
                    </div>
                  ))}
                </div>

                <button 
                  onClick={analyze} 
                  disabled={!!loadingState}
                  className={`w-full mt-6 text-white font-bold py-3 rounded transition-colors ${loadingState ? 'bg-gray-600' : 'bg-blue-600 hover:bg-blue-500'}`}
                >
                  {loadingState || "ANALYZE TRANSACTION"}
                </button>
              </div>
            ) : (
              <div className="bg-gray-800 p-6 rounded-lg border border-gray-700 shadow-xl">
                <h2 className="text-xl font-bold mb-4 text-blue-400">AUTOMATED PROTECTION</h2>
                <div className="text-sm text-gray-400 mb-4">
                  DEMONSTRATION / SIMULATION MODE. This will automatically generate and process realistic test transactions against the existing risk engine.
                </div>
                
                <div className="space-y-4">
                  <div className={`p-4 rounded-lg font-bold text-center text-lg ${autoRunning ? 'bg-green-900 text-green-300 border border-green-700' : 'bg-gray-700 text-gray-400'}`}>
                    AUTOMATED PROTECTION: {autoRunning ? '🟢 ACTIVE' : '🔴 INACTIVE'}
                  </div>
                  
                  {autoRunning ? (
                    <button 
                      onClick={() => setAutoRunning(false)}
                      className="w-full py-3 rounded bg-gray-700 hover:bg-gray-600 text-white font-bold"
                    >
                      STOP PROTECTION
                    </button>
                  ) : (
                    <button 
                      onClick={() => setAutoRunning(true)}
                      className="w-full py-3 rounded bg-blue-600 hover:bg-blue-500 text-white font-bold"
                    >
                      START PROTECTION
                    </button>
                  )}
                </div>
                
                <h3 className="mt-8 text-lg font-bold text-cyan-400 mb-2">DASHBOARD STATS</h3>
                <div className="space-y-2 text-sm font-mono bg-gray-900 p-4 rounded border border-gray-700">
                  <div className="flex justify-between"><span>Total Transactions:</span> <span className="text-white">{autoStats.total}</span></div>
                  <div className="flex justify-between"><span>Analyzed:</span> <span className="text-white">{autoStats.analyzed}</span></div>
                  <div className="flex justify-between"><span>Low Risk:</span> <span className="text-green-400">{autoStats.low}</span></div>
                  <div className="flex justify-between"><span>Medium Risk:</span> <span className="text-yellow-400">{autoStats.medium}</span></div>
                  <div className="flex justify-between"><span>High Risk:</span> <span className="text-red-400">{autoStats.high}</span></div>
                  <div className="flex justify-between mt-2 pt-2 border-t border-gray-800"><span>Allowed:</span> <span className="text-green-400">{autoStats.allowed}</span></div>
                  <div className="flex justify-between"><span>Flagged:</span> <span className="text-orange-400">{autoStats.flagged}</span></div>
                  <div className="flex justify-between"><span>Blocked:</span> <span className="text-red-400">{autoStats.blocked}</span></div>
                </div>
              </div>
            )}
          </div>

          {/* Center Column: Results or Integration Docs */}
          <div className="lg:col-span-1 space-y-6">
            {activeTab === 'manual' ? (
              <>
                {error && (
                  <div className="bg-red-900/50 border border-red-700 text-red-200 p-4 rounded-lg shadow-xl text-sm mb-4">
                    <span className="font-bold block mb-1">Notice:</span>
                    {error}
                  </div>
                )}
                {result ? (
                  <>
                    <div className="bg-gray-800 p-6 rounded-lg border border-gray-700 shadow-xl">
                      <h2 className="text-xl font-bold mb-4 text-blue-400">RISK RESULT</h2>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <div className="text-gray-400 text-xs">FRAUD PROBABILITY</div>
                          <div className="text-2xl font-mono">{(result.ml_probability * 100).toFixed(1)}%</div>
                        </div>
                        <div>
                          <div className="text-gray-400 text-xs">RISK SCORE</div>
                          <div className="text-2xl font-mono">{result.final_score}/100</div>
                        </div>
                      </div>
                      <div className="mt-4 p-4 rounded text-center font-bold text-lg bg-gray-900 border border-gray-700">
                        <span className={result.risk_level === 'SAFE' ? 'text-green-400' : result.risk_level === 'CRITICAL' ? 'text-red-500' : 'text-yellow-400'}>
                          {result.risk_level}
                        </span>
                      </div>
                    </div>

                    <div className="bg-gray-800 p-6 rounded-lg border border-gray-700 shadow-xl">
                      <h2 className="text-xl font-bold mb-4 text-purple-400">POLICY DECISION</h2>
                      <div className="space-y-2">
                        <div className="flex justify-between border-b border-gray-700 pb-2">
                          <span className="text-gray-400">Policy Action</span>
                          <span className="font-mono">{result.policy_action}</span>
                        </div>
                        <div className="flex justify-between border-b border-gray-700 pb-2">
                          <span className="text-gray-400">Authorization State</span>
                          <span className="font-mono text-blue-300">{result.authorization_state}</span>
                        </div>
                        <div className="flex justify-between border-b border-gray-700 pb-2">
                          <span className="text-gray-400">Execution Status</span>
                          <span className="font-mono">{result.execution_status}</span>
                        </div>
                        {result.human_approval_required && (
                          <div className="mt-4 bg-orange-900 text-orange-200 p-3 rounded font-bold text-center animate-pulse">
                            HUMAN APPROVAL REQUIRED
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="bg-gray-800 p-6 rounded-lg border border-gray-700 shadow-xl">
                      <h2 className="text-xl font-bold mb-4 text-red-400">RISK SIGNALS</h2>
                      {result.rule_signals?.length > 0 ? (
                        <ul className="list-disc pl-5 space-y-1 text-red-300 font-mono text-sm">
                          {result.rule_signals.map((s: string, i: number) => <li key={i}>{s}</li>)}
                        </ul>
                      ) : (
                        <div className="text-gray-500 italic">No deterministic signals triggered.</div>
                      )}
                    </div>
                  </>
                ) : (
                  <div className="bg-gray-800 p-6 rounded-lg border border-gray-700 h-full flex items-center justify-center text-gray-500">
                      Submit a transaction to see results.
                  </div>
                )}
              </>
            ) : (
              <div className="bg-gray-800 p-6 rounded-lg border border-gray-700 shadow-xl h-full overflow-y-auto max-h-[800px]">
                <h2 className="text-xl font-bold mb-4 text-purple-400">REAL-TIME SIMULATION FEED</h2>
                
                <div className="space-y-4 text-sm">
                  {autoTransactions.length === 0 ? (
                     <div className="text-gray-500 italic">Click START PROTECTION to begin receiving transactions.</div>
                  ) : (
                     autoTransactions.map((item, idx) => (
                       <div key={idx} className="bg-gray-900 p-4 rounded border border-gray-700 flex flex-col space-y-1">
                          <div className="flex justify-between border-b border-gray-800 pb-2 mb-2">
                             <span className="font-bold text-white">{item.tx.transaction_id}</span>
                             <span className="text-xs text-blue-400 font-bold border border-blue-400/30 bg-blue-900/20 px-2 py-0.5 rounded">DEMO / SIMULATED TRANSACTION</span>
                          </div>
                          <div><span className="text-gray-400">Amount:</span> ${item.tx.amount}</div>
                          <div><span className="text-gray-400">Risk Score:</span> {item.result.final_score}/100</div>
                          <div><span className="text-gray-400">Risk:</span> <span className={item.result.risk_level === 'SAFE' || item.result.risk_level === 'LOW' ? 'text-green-400' : item.result.risk_level === 'SUSPICIOUS' || item.result.risk_level === 'MEDIUM' ? 'text-yellow-400' : 'text-red-400'}>{item.result.risk_level}</span></div>
                          <div><span className="text-gray-400">Decision:</span> <span className={item.result.policy_action === 'ALLOW' ? 'text-green-400' : item.result.policy_action === 'BLOCK' || item.result.policy_action === 'BLOCK_MERCHANT' ? 'text-red-400' : 'text-orange-400'}>{item.result.policy_action}</span></div>
                       </div>
                     ))
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Right Column: System Status */}
          <div className="lg:col-span-1 space-y-6">
            <div className="bg-gray-800 p-6 rounded-lg border border-gray-700 shadow-xl">
              <h2 className="text-xl font-bold mb-4 text-cyan-400">SYSTEM HEALTH & CONTROLS</h2>
              {systemState ? (
                <div className="space-y-2 text-sm font-mono">
                  <div className="flex justify-between"><span>System Mode:</span> <span className={systemState.system_state === 'NORMAL' ? 'text-green-400' : 'text-red-500'}>{systemState.system_state}</span></div>
                  <div className="flex justify-between"><span>Redis Broker:</span> <span className="text-green-400">{systemState.redis_status}</span></div>
                  <div className="flex justify-between"><span>Event Bus:</span> <span className="text-green-400">{systemState.event_bus_status}</span></div>
                  
                  <div className="mt-6 border-t border-gray-700 pt-4">
                    <h3 className="text-xs text-gray-400 mb-2">ADMIN CONTROLS</h3>
                    <button 
                      onClick={() => toggleKillSwitch(systemState.system_state === 'NORMAL')}
                      className={`w-full py-2 rounded text-xs font-bold transition-colors ${systemState.system_state === 'NORMAL' ? 'bg-red-900 text-red-200 hover:bg-red-800' : 'bg-green-900 text-green-200 hover:bg-green-800'}`}
                    >
                      {systemState.system_state === 'NORMAL' ? 'ACTIVATE KILL SWITCH' : 'DEACTIVATE KILL SWITCH'}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="text-gray-500">Loading system state...</div>
              )}
            </div>

            <div className="bg-gray-800 p-6 rounded-lg border border-gray-700 shadow-xl">
              <h2 className="text-xl font-bold mb-4 text-emerald-400">SYSTEM TRACE (AUDIT)</h2>
              <div className="space-y-3 font-mono text-xs">
                {systemState?.recent_events?.length > 0 ? (
                  [...systemState.recent_events].reverse().map((ev: any, i: number) => (
                    <div key={i} className="border-l-2 border-emerald-500 pl-2 py-1 bg-gray-900 rounded">
                      <div className="text-emerald-400 font-bold">{ev.event_type}</div>
                      <div className="text-gray-500 truncate">ID: {ev.correlation_id}</div>
                      <div className="text-gray-400 mt-1 truncate">{JSON.stringify(ev.payload).substring(0, 100)}...</div>
                    </div>
                  ))
                ) : (
                  <div className="text-gray-500 italic">No recent events.</div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
