package app.storylens.protocol;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

public final class Rpc {
    private Rpc(){}
    private static final Set<String> METHODS=Set.of("state","create_chat","chat","send","stop","upload_begin","upload_chunk","upload_finish","file_info","file_chunk");
    public static void validateId(String id){try{if(!UUID.fromString(id).toString().equals(id))throw new IllegalArgumentException();}catch(Exception e){throw new IllegalArgumentException("Invalid request ID.");}}
    public static Map<String,Object> request(String id,String method,Map<String,Object> params){
        validateId(id);if(!METHODS.contains(method))throw new IllegalArgumentException("Unsupported phone command.");
        Map<String,Object> r=new LinkedHashMap<>();r.put("id",id);r.put("method",method);r.put("params",params);return r;
    }
    public static boolean isReadOnly(String method){return Set.of("state","chat","file_info","file_chunk").contains(method);}
}
