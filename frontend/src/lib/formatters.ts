/**
 * Formatting and Market-Time helpers for Intraday-Bot Frontend.
 * All time calculations are strictly referenced to Indian Standard Time (IST, UTC+05:30).
 */

export function formatINR(val: number | null | undefined, includeSymbol: boolean = true): string {
  if (val === null || val === undefined || isNaN(val)) {
    return '—';
  }
  const formatted = new Intl.NumberFormat('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(val);

  return includeSymbol ? `₹${formatted}` : formatted;
}

export function formatSignedINR(val: number | null | undefined): string {
  if (val === null || val === undefined || isNaN(val)) {
    return '—';
  }
  const formatted = formatINR(Math.abs(val));
  if (val > 0) return `+${formatted}`;
  if (val < 0) return `-${formatted}`;
  return formatted;
}

export function formatPct(val: number | null | undefined, includeSign: boolean = true): string {
  if (val === null || val === undefined || isNaN(val)) {
    return '—';
  }
  const sign = includeSign && val > 0 ? '+' : '';
  return `${sign}${val.toFixed(2)}%`;
}

export function formatISTTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    return new Intl.DateTimeFormat('en-IN', {
      timeZone: 'Asia/Kolkata',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    }).format(d) + ' IST';
  } catch {
    return dateStr;
  }
}

export function formatISTDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    return new Intl.DateTimeFormat('en-IN', {
      timeZone: 'Asia/Kolkata',
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    }).format(d);
  } catch {
    return dateStr;
  }
}

export function formatISTDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    return new Intl.DateTimeFormat('en-IN', {
      timeZone: 'Asia/Kolkata',
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).format(d) + ' IST';
  } catch {
    return dateStr;
  }
}

export function timeAgo(dateStr: string | null | undefined): string {
  if (!dateStr) return 'never';
  try {
    const past = new Date(dateStr).getTime();
    const now = Date.now();
    const diffSec = Math.floor((now - past) / 1000);

    if (diffSec < 10) return 'just now';
    if (diffSec < 60) return `${diffSec}s ago`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHours = Math.floor(diffMin / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  } catch {
    return '—';
  }
}

export interface MarketSessionStatus {
  isOpen: boolean;
  statusText: string;
  badgeColor: 'emerald' | 'amber' | 'slate' | 'rose';
  nextEventText: string;
}

export function getMarketSessionStatus(): MarketSessionStatus {
  // Compute current time in IST
  const now = new Date();
  const utcMs = now.getTime() + now.getTimezoneOffset() * 60000;
  const istNow = new Date(utcMs + 5.5 * 3600000);

  const day = istNow.getDay(); // 0 is Sunday, 6 is Saturday
  const hour = istNow.getHours();
  const minute = istNow.getMinutes();
  const currentMinutes = hour * 60 + minute;

  // Weekend
  if (day === 0 || day === 6) {
    return {
      isOpen: false,
      statusText: 'MARKET CLOSED (WEEKEND)',
      badgeColor: 'slate',
      nextEventText: 'Opens Monday 09:15 IST',
    };
  }

  // Weekdays
  const premarketStart = 8 * 60 + 30; // 08:30
  const marketOpen = 9 * 60 + 15;     // 09:15
  const entryCutoff = 14 * 60 + 45;   // 14:45
  const squareOff = 15 * 60 + 15;     // 15:15
  const marketClose = 15 * 60 + 30;   // 15:30
  const postmarketEnd = 16 * 60 + 30; // 16:30

  if (currentMinutes < premarketStart) {
    return {
      isOpen: false,
      statusText: 'MARKET CLOSED',
      badgeColor: 'slate',
      nextEventText: 'Pre-market research at 08:30 IST',
    };
  } else if (currentMinutes < marketOpen) {
    return {
      isOpen: false,
      statusText: 'PRE-MARKET SESSION',
      badgeColor: 'amber',
      nextEventText: 'Regular trading opens at 09:15 IST',
    };
  } else if (currentMinutes < entryCutoff) {
    return {
      isOpen: true,
      statusText: 'MARKET OPEN',
      badgeColor: 'emerald',
      nextEventText: 'Entry cutoff at 14:45 IST',
    };
  } else if (currentMinutes < squareOff) {
    return {
      isOpen: true,
      statusText: 'EXIT ONLY (ENTRY CUTOFF)',
      badgeColor: 'amber',
      nextEventText: 'Square-off triggers at 15:15 IST',
    };
  } else if (currentMinutes < marketClose) {
    return {
      isOpen: true,
      statusText: 'SQUARE-OFF WINDOW',
      badgeColor: 'rose',
      nextEventText: 'Market close at 15:30 IST',
    };
  } else if (currentMinutes < postmarketEnd) {
    return {
      isOpen: false,
      statusText: 'POST-MARKET ANALYSIS',
      badgeColor: 'slate',
      nextEventText: 'Overnight research at 23:00 IST',
    };
  } else {
    return {
      isOpen: false,
      statusText: 'MARKET CLOSED',
      badgeColor: 'slate',
      nextEventText: 'Overnight global research at 23:00 IST',
    };
  }
}
