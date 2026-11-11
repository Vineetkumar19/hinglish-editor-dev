package app.storylens.phone;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import app.storylens.protocol.Codec;
import app.storylens.protocol.Pairing;

final class PairingStore {
    private static final String ALIAS="storylens.personal.pairing.v1";
    private final SharedPreferences preferences;
    PairingStore(Context c){preferences=c.getSharedPreferences("sealed_pairing",Context.MODE_PRIVATE);}
    private SecretKey key()throws Exception{
        KeyStore store=KeyStore.getInstance("AndroidKeyStore");store.load(null);
        if(store.containsAlias(ALIAS))return (SecretKey)store.getKey(ALIAS,null);
        KeyGenerator generator=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(ALIAS,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).setKeySize(256).setRandomizedEncryptionRequired(true).build());
        return generator.generateKey();
    }
    void save(String code)throws Exception{
        Pairing.parse(code);Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,key());cipher.updateAAD(ALIAS.getBytes(StandardCharsets.UTF_8));
        String encrypted=Codec.encode(cipher.doFinal(code.getBytes(StandardCharsets.UTF_8)));
        if(!preferences.edit().putString("iv",Codec.encode(cipher.getIV())).putString("ciphertext",encrypted).commit())throw new java.io.IOException("Unable to save the private connection.");
    }
    Pairing load()throws Exception{
        String encrypted=preferences.getString("ciphertext",null);if(encrypted==null)return null;
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Codec.decode(preferences.getString("iv",""))));cipher.updateAAD(ALIAS.getBytes(StandardCharsets.UTF_8));
        return Pairing.parse(new String(cipher.doFinal(Codec.decode(encrypted)),StandardCharsets.UTF_8));
    }
    void forget()throws Exception{
        if(!preferences.edit().clear().commit())throw new java.io.IOException("Connection could not be removed.");
        KeyStore store=KeyStore.getInstance("AndroidKeyStore");store.load(null);if(store.containsAlias(ALIAS))store.deleteEntry(ALIAS);
    }
}
