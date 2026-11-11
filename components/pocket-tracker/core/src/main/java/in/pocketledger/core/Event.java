package in.pocketledger.core;

public final class Event {
    public final Message message;
    public long paise, time;
    public String direction="", account="", bank="", reference="", merchant="", kind="Unclassified", status="posted";
    public String instrument="unknown", paymentApp="", channel="";
    public String risk="", issue="", note="";
    public boolean financial, exactTime;
    public Event(Message message) { this.message=message; this.time=message.receivedAt; }
    public boolean eligible() { return financial && paise>0 && !direction.isEmpty() && status.equals("posted") && risk.isEmpty() && issue.isEmpty(); }
}
