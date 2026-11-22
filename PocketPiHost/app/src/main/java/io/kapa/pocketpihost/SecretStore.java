package io.kapa.pocketpihost;
import android.content.Context;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
final class SecretStore {
 private static final String ALIAS="PocketPiHoleTokenKey";
 static SecretKey key() throws Exception {
   KeyStore ks=KeyStore.getInstance("AndroidKeyStore"); ks.load(null);
   if (ks.containsAlias(ALIAS)) return ((KeyStore.SecretKeyEntry)ks.getEntry(ALIAS,null)).getSecretKey();
   KeyGenerator gen=KeyGenerator.getInstance("AES","AndroidKeyStore");
   gen.init(new KeyGenParameterSpec.Builder(ALIAS,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT).setBlockModes("GCM").setEncryptionPaddings("NoPadding").build());
   return gen.generateKey();
 }
 static void save(Context context,String value) throws Exception {
   if (!value.matches("[a-fA-F0-9]{64}")) throw new Exception("Enter the 64-character VM token.");
   Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding"); cipher.init(Cipher.ENCRYPT_MODE,key());
   byte[] data=cipher.doFinal(value.getBytes(StandardCharsets.UTF_8));
   context.getSharedPreferences("secret",0).edit().putString("iv",Base64.encodeToString(cipher.getIV(),2)).putString("data",Base64.encodeToString(data,2)).apply();
 }
 static String load(Context context) throws Exception {
   var p=context.getSharedPreferences("secret",0); String iv=p.getString("iv",""),data=p.getString("data","");
   if (iv.isEmpty()||data.isEmpty()) return "";
   Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
   cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Base64.decode(iv,2)));
   return new String(cipher.doFinal(Base64.decode(data,2)),StandardCharsets.UTF_8);
 }
}
