package app.storylens.protocol;

import java.util.Map;

public final class Transfer {
    private Transfer(){}
    public static final int CHUNK=128*1024;
    public static final long MAX_FILE=256L*1024*1024;
    public static void validateSize(long size){if(size<0||size>MAX_FILE)throw new IllegalArgumentException("Phone files must be 256 MiB or smaller. Use the laptop for larger files.");}
    public static byte[] chunk(Map<String,Object> value,long offset,int requested,long total){
        validateSize(total);if(requested<1||requested>CHUNK||offset<0||offset>total)throw new IllegalArgumentException("Invalid file request.");
        byte[] data=Codec.decode(Json.string(value,"data"));
        if(data.length>requested||data.length==0&&offset<total||Json.integer(value,"offset")!=offset||Json.integer(value,"next_offset")!=offset+data.length||offset+data.length>total||!(value.get("eof") instanceof Boolean)||((Boolean)value.get("eof"))!=(offset+data.length==total))throw new IllegalArgumentException("File chunk was incomplete or out of order. Nothing was saved.");
        return data;
    }
    public static String safeName(String name){
        String clean=name.replace('\\','/');clean=clean.substring(clean.lastIndexOf('/')+1).replaceAll("[\\p{Cntrl}<>:\"|?*]","_");
        if(clean.isBlank()||clean.equals(".")||clean.equals(".."))clean="StoryLens-file";
        return clean.length()>140?clean.substring(clean.length()-140):clean;
    }
}
