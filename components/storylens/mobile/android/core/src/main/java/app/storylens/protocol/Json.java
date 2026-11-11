package app.storylens.protocol;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Small strict JSON codec shared with the dependency-free protocol checks. */
public final class Json {
    private Json() {}
    public static final int MAX_JSON = 2 * 1024 * 1024;
    public static Object parse(String text) {
        if (text == null || text.length() > MAX_JSON) throw new IllegalArgumentException("Message is too large.");
        Reader r = new Reader(text); Object value = r.value(0); r.space();
        if (r.pos != text.length()) throw new IllegalArgumentException("Invalid JSON suffix.");
        return value;
    }
    @SuppressWarnings("unchecked") public static Map<String,Object> object(Object value) {
        if (!(value instanceof Map)) throw new IllegalArgumentException("Expected an object.");
        return (Map<String,Object>)value;
    }
    public static String string(Map<String,Object> value, String key) {
        Object found = value.get(key);
        if (!(found instanceof String)) throw new IllegalArgumentException("Missing text field: " + key);
        return (String)found;
    }
    public static long integer(Map<String,Object> value, String key) {
        Object found = value.get(key);
        if (!(found instanceof Long || found instanceof Integer)) throw new IllegalArgumentException("Missing integer field: " + key);
        return ((Number)found).longValue();
    }
    public static String stringify(Object value) { StringBuilder out = new StringBuilder(); write(out,value,0); return out.toString(); }
    private static void write(StringBuilder out, Object v, int depth) {
        if (depth > 32) throw new IllegalArgumentException("JSON is too deeply nested.");
        if (v == null) out.append("null");
        else if(v instanceof String) {
            out.append('"'); String s = (String)v;
            for(int i=0;i<s.length();i++) { char c=s.charAt(i); switch(c) {
                case '"': out.append("\\\""); break; case '\\': out.append("\\\\"); break;
                case '\n': out.append("\\n"); break; case '\r': out.append("\\r"); break; case '\t': out.append("\\t"); break;
                default: if(c<32) out.append(String.format(java.util.Locale.ROOT,"\\u%04x",(int)c)); else out.append(c);
            }} out.append('"');
        } else if(v instanceof Boolean || v instanceof Integer || v instanceof Long) out.append(v);
        else if(v instanceof Number) { double n=((Number)v).doubleValue(); if(Double.isNaN(n)||Double.isInfinite(n)) throw new IllegalArgumentException("Invalid number."); out.append(v); }
        else if(v instanceof Map) { out.append('{'); boolean first=true; for(Map.Entry<?,?> e:((Map<?,?>)v).entrySet()) { if(!(e.getKey() instanceof String)) throw new IllegalArgumentException("Invalid object key."); if(!first)out.append(','); first=false; write(out,e.getKey(),depth+1);out.append(':');write(out,e.getValue(),depth+1); } out.append('}'); }
        else if(v instanceof Iterable) { out.append('[');boolean first=true;for(Object item:(Iterable<?>)v){if(!first)out.append(',');first=false;write(out,item,depth+1);}out.append(']'); }
        else throw new IllegalArgumentException("Unsupported JSON value.");
        if(out.length()>MAX_JSON)throw new IllegalArgumentException("Message is too large.");
    }
    private static final class Reader {
        final String s; int pos;
        Reader(String s){this.s=s;}
        void space(){while(pos<s.length() && (s.charAt(pos)==' '||s.charAt(pos)=='\n'||s.charAt(pos)=='\r'||s.charAt(pos)=='\t'))pos++;}
        IllegalArgumentException bad(){return new IllegalArgumentException("Invalid JSON message.");}
        Object value(int depth){
            if(depth>32)throw bad();space();if(pos>=s.length())throw bad();char c=s.charAt(pos);
            if(c=='"')return text();
            if(c=='{'){pos++;Map<String,Object> m=new LinkedHashMap<>();space();if(take('}'))return m; do {space();if(pos>=s.length()||s.charAt(pos)!='"')throw bad();String k=text();space();if(!take(':')||m.containsKey(k))throw bad();m.put(k,value(depth+1));space();if(take('}'))return m;}while(take(','));throw bad();}
            if(c=='['){pos++;List<Object>a=new ArrayList<>();space();if(take(']'))return a;do{a.add(value(depth+1));space();if(take(']'))return a;}while(take(','));throw bad();}
            for(String word:new String[]{"true","false","null"})if(s.startsWith(word,pos)){pos+=word.length();return word.equals("null")?null:word.equals("true");}
            int start=pos;if(take('-')&&pos>=s.length())throw bad();if(take('0')){}else{if(pos>=s.length()||s.charAt(pos)<'1'||s.charAt(pos)>'9')throw bad();while(pos<s.length()&&digit(s.charAt(pos)))pos++;}
            boolean decimal=false;if(take('.')){decimal=true;int p=pos;while(pos<s.length()&&digit(s.charAt(pos)))pos++;if(p==pos)throw bad();}
            if(take('e')||take('E')){decimal=true;if(!take('+'))take('-');int p=pos;while(pos<s.length()&&digit(s.charAt(pos)))pos++;if(p==pos)throw bad();}
            try {String num=s.substring(start,pos);if(decimal){double n=Double.parseDouble(num);if(Double.isInfinite(n)||Double.isNaN(n))throw bad();return n;}return Long.parseLong(num);}catch(NumberFormatException e){throw bad();}
        }
        boolean digit(char c){return c>='0'&&c<='9';}
        boolean take(char c){if(pos<s.length()&&s.charAt(pos)==c){pos++;return true;}return false;}
        String text(){if(!take('"'))throw bad();StringBuilder b=new StringBuilder();while(pos<s.length()){char c=s.charAt(pos++);if(c=='"')return b.toString();if(c<32)throw bad();if(c=='\\'){if(pos>=s.length())throw bad();c=s.charAt(pos++);switch(c){case '"':case '\\':case '/':break;case 'b':c='\b';break;case 'f':c='\f';break;case 'n':c='\n';break;case 'r':c='\r';break;case 't':c='\t';break;case 'u':if(pos+4>s.length())throw bad();try{c=(char)Integer.parseInt(s.substring(pos,pos+4),16);}catch(NumberFormatException e){throw bad();}pos+=4;break;default:throw bad();}}b.append(c);}throw bad();}
    }
}
