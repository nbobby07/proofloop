import { API_BASE_URL } from '../../services/api';

const key = `proofloop:v1:${API_BASE_URL}:`;
export function readSelection(name: string): string {
  try { return sessionStorage.getItem(key + name) ?? ''; } catch { return ''; }
}
export function saveSelection(name: string, value: string) {
  try { sessionStorage.setItem(key + name, value); } catch { /* Storage is optional. */ }
}
export function savedRunId() {
  const value = readSelection('run');
  return /^[A-Za-z0-9_-]{1,128}$/.test(value) ? value : '';
}
