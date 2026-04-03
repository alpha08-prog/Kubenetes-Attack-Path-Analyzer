import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import LiveCveFeedPanel from "@/components/LiveCveFeedPanel";

export default function LiveCveFeedPage() {
  const navigate = useNavigate();

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden p-3 sm:p-4 md:p-6 gap-3 md:gap-4">
      <header className="flex-shrink-0 flex items-center gap-3 border-b border-border pb-3 md:pb-4">
        <button
          onClick={() => navigate("/")}
          className="flex items-center gap-2 bg-secondary hover:bg-surface-hover text-foreground px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Dashboard
        </button>
        <span className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-primary to-emerald-400">
          Vulnerability Intelligence
        </span>
      </header>

      <div className="flex-1 min-h-0 w-full max-w-7xl mx-auto rounded-xl border border-border bg-card overflow-hidden shadow-2xl shadow-primary/5">
        <LiveCveFeedPanel />
      </div>
    </div>
  );
}
