export function riskToColor(risk: number): string {
  if (risk >= 8) return '#E24B4A';
  if (risk >= 6) return '#EF9F27';
  if (risk >= 4) return '#378ADD';
  return '#1D9E75';
}

export function riskToSize(risk: number, min = 30, max = 60): number {
  return min + ((risk / 10) * (max - min));
}

export function riskToWidth(risk: number, min = 1, max = 4): number {
  return min + ((risk / 10) * (max - min));
}
