class FloAlertsCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity) throw new Error("Specify the Flo active alerts sensor");
    this.config = config;
  }
  getCardSize() { return 5; }
  set hass(hass) {
    this._hass = hass;
    if (!this.busy) this.render();
  }
  render() {
    if (!this.config || !this._hass) return;
    const state = this._hass.states[this.config.entity];
    const card = document.createElement("ha-card");
    const body = document.createElement("div");
    body.style.cssText = "padding:16px;display:grid;gap:12px";
    const add = (parent, tag, text) => {
      const el = document.createElement(tag);
      el.textContent = text;
      parent.append(el);
      return el;
    };
    const button = (parent, label, action, disabled=false) => {
      const el = add(parent, "button", label);
      el.style.cssText = "padding:10px;border:1px solid var(--divider-color);border-radius:8px;background:var(--card-background-color);color:var(--primary-text-color);cursor:pointer";
      el.disabled = disabled || !!this.busy;
      el.onclick = action;
      return el;
    };
    add(body, "h2", this.config.title || "Moen Flo alerts");
    const attrs = state?.attributes || {};
    const valid = state && !["unknown","unavailable"].includes(state.state) && Array.isArray(attrs.alerts) && attrs.location_id;
    const alerts = valid ? attrs.alerts : [];
    const admin = !!this._hass.user?.is_admin;
    const call = async (action, data) => {
      this.busy = true;
      this.error = "";
      this.render();
      try {
        await this._hass.callService("flo_alerts", action, {location_id: attrs.location_id, ...data});
        if (action !== "refresh") await this._hass.callService("flo_alerts", "refresh", {location_id: attrs.location_id});
      } catch (err) { this.error = err.message || String(err); }
      finally { this.busy = false; this.render(); }
    };
    if (!valid) add(body, "p", "Alert data unavailable. Do not assume there are no alerts.");
    else {
      add(body, "strong", alerts.length + " outstanding · " + attrs.critical_count + " critical");
      if (!alerts.length) add(body, "p", "No outstanding warning or critical alerts.");
      for (const alert of alerts) {
        const section = document.createElement("section");
        section.style.cssText = "border:1px solid var(--divider-color);border-radius:12px;padding:12px;display:grid;gap:8px";
        const heading = add(section, "strong", alert.title || "Flo alert");
        heading.style.color = alert.severity === "critical" ? "var(--error-color)" : "var(--warning-color)";
        add(section, "small", alert.severity + " · " + (alert.created_at ? new Date(alert.created_at).toLocaleString() : ""));
        add(section, "div", alert.message || "");
        const same = alerts.filter(a => a.alarm_id === alert.alarm_id);
        button(section, same.length > 1 ? "Acknowledge " + same.length + " alerts of this type" : "Acknowledge alert", () => {
          if (window.confirm("Have you investigated the cause? Acknowledge " + same.length + " alert(s) of this type?")) call("clear_alert", {alarm_id: alert.alarm_id, event_ids: same.map(a => a.event_id)});
        }, !admin);
        body.append(section);
      }
    }
    if (this.error) add(body, "p", this.error).style.color = "var(--error-color)";
    const footer = document.createElement("div");
    footer.style.cssText = "display:flex;gap:8px;flex-wrap:wrap";
    button(footer, "Refresh", () => call("refresh", {}), !attrs.location_id || !admin);
    button(footer, "Clear all alerts", () => {
      if (window.confirm("Have you investigated all " + alerts.length + " outstanding alerts? Acknowledge them all?")) call("clear_all_alerts", {event_ids: alerts.map(a => a.event_id)});
    }, !valid || !alerts.length || !admin);
    body.append(footer);
    card.append(body);
    this.replaceChildren(card);
  }
}
if (!customElements.get("flo-alerts-card")) customElements.define("flo-alerts-card", FloAlertsCard);
window.customCards = window.customCards || [];
window.customCards.push({type:"flo-alerts-card",name:"Flo Alerts",description:"Review and acknowledge outstanding Moen Flo alerts"});
