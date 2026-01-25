export type PaymentCurrencyAmount = {
  currency: string;
  value: number;
};

export type PaymentItem = {
  label: string;
  amount: PaymentCurrencyAmount;
  pending?: boolean;
  refundPeriod: number;
};
