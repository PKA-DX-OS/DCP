// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import type { CongTrinhCache, FieldDraft } from "./field-inspection";

/**
 * Kho nháp hiện trường: IndexedDB cho ảnh/chữ ký; nếu trình duyệt chặn thì giữ trong bộ nhớ
 * của tab. Không gửi dữ liệu lên máy chủ.
 */

const DB_NAME = "dxos-field-db";
const DB_VERSION = 1;
const KHO_NHAP = "drafts";
const KHO_META = "meta";

const nhoNhap = new Map<string, FieldDraft>();
const nhoMeta = new Map<string, unknown>();
let dbPromise: Promise<IDBDatabase | null> | null = null;

function moDb(): Promise<IDBDatabase | null> {
  if (typeof indexedDB === "undefined") return Promise.resolve(null);
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve) => {
    try {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(KHO_NHAP)) {
          const store = db.createObjectStore(KHO_NHAP, { keyPath: "id" });
          store.createIndex("updatedAt", "updatedAt");
        }
        if (!db.objectStoreNames.contains(KHO_META)) {
          db.createObjectStore(KHO_META, { keyPath: "key" });
        }
      };
      req.onsuccess = () => {
        const db = req.result;
        db.onversionchange = () => db.close();
        resolve(db);
      };
      req.onerror = () => resolve(null);
      req.onblocked = () => resolve(null);
    } catch {
      resolve(null);
    }
  });
  return dbPromise;
}

function yeuCau<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function voiKho<T>(
  ten: string,
  mode: IDBTransactionMode,
  fn: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T | null> {
  const db = await moDb();
  if (!db) return null;
  try {
    const tx = db.transaction(ten, mode);
    const store = tx.objectStore(ten);
    const hoanTat = new Promise<void>((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error);
    });
    const req = fn(store);
    const ketQua = await yeuCau(req);
    await hoanTat;
    return ketQua;
  } catch {
    return null;
  }
}

export async function luuNhap(d: FieldDraft): Promise<void> {
  nhoNhap.set(d.id, d);
  await voiKho(KHO_NHAP, "readwrite", (store) => store.put(d));
}

export async function docNhap(id: string): Promise<FieldDraft | null> {
  if (nhoNhap.has(id)) return nhoNhap.get(id) || null;
  const d = await voiKho<FieldDraft | undefined>(KHO_NHAP, "readonly", (store) => store.get(id));
  if (d) nhoNhap.set(d.id, d);
  return d || null;
}

export async function taiDsNhap(): Promise<FieldDraft[]> {
  const tuDb = (await voiKho<FieldDraft[]>(KHO_NHAP, "readonly", (store) => store.getAll())) || [];
  const hopNhat = new Map<string, FieldDraft>();
  for (const d of tuDb) hopNhat.set(d.id, d);
  for (const [id, d] of nhoNhap) hopNhat.set(id, d);
  return Array.from(hopNhat.values()).sort((a, b) => b.updatedAt - a.updatedAt);
}

export async function xoaNhap(id: string): Promise<void> {
  nhoNhap.delete(id);
  await voiKho(KHO_NHAP, "readwrite", (store) => store.delete(id));
}

export async function xoaTatCaNhap(): Promise<void> {
  nhoNhap.clear();
  await voiKho(KHO_NHAP, "readwrite", (store) => store.clear());
}

export async function luuCacheCongTrinh(ds: CongTrinhCache[]): Promise<void> {
  nhoMeta.set("cong-trinh", ds);
  await voiKho(KHO_META, "readwrite", (store) => store.put({ key: "cong-trinh", value: ds }));
}

export async function docCacheCongTrinh(): Promise<CongTrinhCache[]> {
  if (nhoMeta.has("cong-trinh")) return (nhoMeta.get("cong-trinh") as CongTrinhCache[]) || [];
  const row = await voiKho<{ key: string; value: CongTrinhCache[] } | undefined>(
    KHO_META,
    "readonly",
    (store) => store.get("cong-trinh"),
  );
  if (row?.value) {
    nhoMeta.set("cong-trinh", row.value);
    return row.value;
  }
  return [];
}

export async function xoaCacheCongTrinh(): Promise<void> {
  nhoMeta.delete("cong-trinh");
  await voiKho(KHO_META, "readwrite", (store) => store.delete("cong-trinh"));
}
