package in.pocketledger.core;

public final class Message {
    public final String id, source, sender, body, safetyLabel;
    public final long receivedAt;
    public Message(String id, String source, String sender, String body, long receivedAt) {
        this(id,source,sender,body,receivedAt,"");
    }
    public Message(String id, String source, String sender, String body, long receivedAt,String safetyLabel) {
        this.id=id; this.source=source; this.sender=sender==null?"":sender;
        this.body=body==null?"":body; this.receivedAt=receivedAt;
        this.safetyLabel=safetyLabel==null?"":safetyLabel;
    }
}
