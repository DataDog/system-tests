package com.datadoghq.system_tests.iast.utils;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;

public class Utils {

    private Utils(){}

    public static String sendGetRequest(String urlStr) {
        URL url = null;
        HttpURLConnection conn = null;
        BufferedReader in = null;
        StringBuilder content = new StringBuilder();

        try {
            url = new URL(urlStr);
            conn = (HttpURLConnection) url.openConnection();

            conn.setRequestMethod("GET");
            conn.setRequestProperty("Content-Type", "application/json");

            int responseCode = conn.getResponseCode();
            if (responseCode == HttpURLConnection.HTTP_OK) { // success
                in = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                String inputLine;

                while ((inputLine = in.readLine()) != null) {
                    content.append(inputLine);
                }
            } else {
                System.out.println("GET request not worked");
            }
        } catch (IOException e) {
            e.printStackTrace();
        } finally {
            try {
                if (in != null) {
                    in.close();
                }
                if (conn != null) {
                    conn.disconnect();
                }
            } catch (IOException ex) {
                ex.printStackTrace();
            }
        }

        return content.toString();
    }

}