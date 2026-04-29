import { useState } from "react";
import type { InventoryMatch, InventoryOptionsArtifact } from "../types";
import "./InventoryOptionsCard.scss";

interface Props {
  inventory: InventoryOptionsArtifact;
  onSelect?: (itemId: string) => void;
}

function ItemRow({
  item,
  selected,
  onClick,
}: {
  item: InventoryMatch;
  selected: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      className={`item-card ${onClick ? "clickable" : ""} ${selected ? "selected" : ""}`}
      type="button"
      onClick={onClick}>
      <span className="row-content">
        {selected && (
          <span className="selected-icon">
            <svg width="8" height="8" viewBox="0 0 8 8">
              <title>Selected</title>
              <path
                d="M1.5 4l2 2 3-3"
                stroke="white"
                strokeWidth="1.5"
                fill="none"
                strokeLinecap="round"
              />
            </svg>
          </span>
        )}
        {!selected && <span className="unselected-circle" />}
        <span className="item-details">
          <span className="item-name">{item.name}</span>
          <span className="item-id">{item.item_id}</span>
        </span>
      </span>
      <span className="price-wrapper">
        <span className="item-price">${item.price.toFixed(2)}</span>
        {item.stock != null && (
          <span className="item-stock">{item.stock} in stock</span>
        )}
      </span>
    </button>
  );
}

export function InventoryOptionsCard({ inventory, onSelect }: Props) {
  const [userSelected, setUserSelected] = useState<string | undefined>(
    inventory.selected
  );
  const [hasConfirmed, setHasConfirmed] = useState(false);
  const selected = userSelected ?? inventory.selected ?? "";
  const canConfirm = !!onSelect && !!selected && !hasConfirmed;

  return (
    <div className="msg-agent inventory-options-container">
      <div className="header-wrapper">
        <div className="icon-wrapper">
          <svg width="10" height="10" viewBox="0 0 10 10">
            <title>Inventory available</title>
            <path
              d="M2 5l2 2 4-4"
              stroke="#34d399"
              strokeWidth="1.5"
              fill="none"
              strokeLinecap="round"
            />
          </svg>
        </div>
        <span className="tool-label">Merchant MCP · search_inventory</span>
      </div>
      <div className="item-list">
        {inventory.matches.map((item) => (
          <ItemRow
            key={item.item_id}
            item={item}
            selected={item.item_id === selected}
            onClick={onSelect ? () => setUserSelected(item.item_id) : undefined}
          />
        ))}
      </div>
      <p className="info-text">
        I&apos;ve queried the merchant inventory via Merchant MCP and found{" "}
        {inventory.matches.length} option
        {inventory.matches.length === 1 ? "" : "s"} above. Please select which
        item you want, then I&apos;ll create the purchase mandate and start
        monitoring the price.
      </p>
      <div className="status-text">
        {onSelect ? (
          selected ? (
            <>
              Selected <span className="selected-item-id">{selected}</span>
              {hasConfirmed
                ? ". Creating mandate…"
                : ". Click &quot;Confirm selection&quot; to create the mandate."}
            </>
          ) : (
            "Choose an option above."
          )
        ) : (
          <>
            Selected <span className="selected-item-id">{selected || "—"}</span>
          </>
        )}
      </div>
      {canConfirm && (
        <button
          type="button"
          onClick={() => {
            setHasConfirmed(true);
            onSelect?.(selected);
          }}
          className="confirm-button">
          Confirm selection
        </button>
      )}
    </div>
  );
}
