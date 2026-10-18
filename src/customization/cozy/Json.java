package cozy;

import java.util.*;

/** Typed facade over the deliberately API-shrunk Gson bundled by upstream. */
class JsonElement {
    final com.google.gson.JsonElement raw;
    JsonElement(com.google.gson.JsonElement raw) { this.raw = raw; }
    static JsonElement wrap(com.google.gson.JsonElement raw) {
        if (raw == null) return null;
        if (raw.isJsonObject()) return new JsonObject(raw.getAsJsonObject());
        if (raw.isJsonArray()) return new JsonArray(raw.getAsJsonArray());
        if (raw.isJsonPrimitive()) return new JsonPrimitive(raw.getAsJsonPrimitive());
        return new JsonElement(raw);
    }
    boolean isJsonObject() { return raw.isJsonObject(); }
    boolean isJsonPrimitive() { return raw.isJsonPrimitive(); }
    boolean isJsonNull() { return raw.isJsonNull(); }
    JsonObject getAsJsonObject() { return (JsonObject)wrap(raw.getAsJsonObject()); }
    JsonArray getAsJsonArray() { return (JsonArray)wrap(raw.getAsJsonArray()); }
    JsonPrimitive getAsJsonPrimitive() { return (JsonPrimitive)wrap(raw.getAsJsonPrimitive()); }
    String getAsString() { return raw.getAsString(); }
    int getAsInt() { return raw.getAsInt(); }
    boolean getAsBoolean() { return raw.getAsJsonPrimitive().getAsBoolean(); }
}

class JsonObject extends JsonElement {
    JsonObject() { super(new com.google.gson.JsonObject()); }
    JsonObject(com.google.gson.JsonObject raw) { super(raw); }
    void add(String key, JsonElement value) { raw.getAsJsonObject().add(key, value == null ? null : value.raw); }
    void addProperty(String key, String value) { add(key, value == null ? null : new JsonPrimitive(value)); }
    void addProperty(String key, boolean value) { add(key, new JsonPrimitive(value)); }
    void addProperty(String key, Number value) { add(key, new JsonPrimitive(value)); }
    JsonElement get(String key) { return wrap(raw.getAsJsonObject().get(key)); }
    boolean has(String key) { return get(key) != null; }
    JsonObject getAsJsonObject(String key) { JsonElement v = get(key); return v == null ? null : v.getAsJsonObject(); }
    JsonArray getAsJsonArray(String key) { return get(key).getAsJsonArray(); }
    Set<Map.Entry<String, JsonElement>> entrySet() {
        Set<Map.Entry<String, JsonElement>> out = new LinkedHashSet<>();
        for (Object v : raw.getAsJsonObject().entrySet()) {
            Map.Entry<?, ?> e = (Map.Entry<?, ?>)v;
            out.add(new AbstractMap.SimpleImmutableEntry<>((String)e.getKey(), wrap((com.google.gson.JsonElement)e.getValue())));
        }
        return out;
    }
    JsonObject deepCopy() {
        return wrap(com.google.gson.JsonParser.parseReader(new java.io.StringReader(raw.toString()))).getAsJsonObject();
    }
}

class JsonArray extends JsonElement implements Iterable<JsonElement> {
    JsonArray() { super(new com.google.gson.JsonArray()); }
    JsonArray(com.google.gson.JsonArray raw) { super(raw); }
    void add(JsonElement value) { raw.getAsJsonArray().add(value.raw); }
    int size() { int size = 0; for (JsonElement ignored : this) size++; return size; }
    public Iterator<JsonElement> iterator() {
        Iterator<?> i = raw.getAsJsonArray().iterator();
        return new Iterator<>() {
            public boolean hasNext() { return i.hasNext(); }
            public JsonElement next() { return wrap((com.google.gson.JsonElement)i.next()); }
        };
    }
}

class JsonPrimitive extends JsonElement {
    JsonPrimitive(com.google.gson.JsonPrimitive raw) { super(raw); }
    JsonPrimitive(String v) { super(new com.google.gson.JsonPrimitive(v)); }
    JsonPrimitive(boolean v) { super(new com.google.gson.JsonPrimitive(v)); }
    JsonPrimitive(Number v) { super(new com.google.gson.JsonPrimitive(v)); }
    boolean isBoolean() { return raw.getAsJsonPrimitive().isBoolean(); }
    boolean isString() { return raw.getAsJsonPrimitive().isString(); }
}
