/** Categorias de activos */
export const ASSET_CATEGORIES = [
  'hardware',
  'peripherals',
  'office_supplies',
  'training_materials',
] as const;
export type AssetCategory = (typeof ASSET_CATEGORIES)[number];

export const ASSET_CATEGORY_LABELS: Record<AssetCategory, string> = {
  hardware: 'Hardware',
  peripherals: 'Periféricos',
  office_supplies: 'Suministros de oficina',
  training_materials: 'Materiales de formación',
};

/** Oficinas disponibles */
export const OFFICES = ['Valencia', 'Miami'] as const;
export type Office = (typeof OFFICES)[number];

/** Tipos de salida */
export const EXIT_TYPES = ['allocation', 'consumption'] as const;
export type ExitType = (typeof EXIT_TYPES)[number];

export const EXIT_TYPE_LABELS: Record<ExitType, string> = {
  allocation: 'Asignación',
  consumption: 'Consumo',
};

/** Product/Asset response */
export interface Product {
  id: number;
  name: string;
  sku: string;
  category: AssetCategory;
  office: Office;
  current_stock: number;
}

/** Inbound order creation payload */
export interface InboundOrderPayload {
  asset_id: number;
  quantity: number;
  supplier: string;
  office: Office;
}

/** Inbound order response */
export interface InboundOrderResponse {
  id: number;
  asset_id: number;
  quantity: number;
  supplier: string;
  office: Office;
  created_at: string;
  user_uuid: string;
}

/** Outbound order creation payload */
export interface OutboundOrderPayload {
  asset_id: number;
  quantity: number;
  exit_type: ExitType;
  assigned_to: string | null;
  office: Office;
}

/** Outbound order response */
export interface OutboundOrderResponse {
  id: number;
  asset_id: number;
  quantity: number;
  exit_type: ExitType;
  assigned_to: string | null;
  office: Office;
  created_at: string;
  user_uuid: string;
}

/** Combined order listing */
export interface Order {
  id: number;
  type: 'entry' | 'exit';
  asset_id: number;
  asset_name: string;
  asset_sku: string;
  quantity: number;
  office: Office;
  user_uuid: string;
  created_at: string;
  supplier: string | null;
  exit_type: ExitType | null;
  assigned_to: string | null;
}