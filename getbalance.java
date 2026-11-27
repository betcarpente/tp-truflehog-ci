@GetMapping("/account/balance")
public String getBalance(@RequestParam("iban") String iban) throws SQLException {
    String sql = "SELECT balance FROM accounts WHERE iban = ?";

    try (Connection conn = dataSource.getConnection();
         PreparedStatement stmt = conn.prepareStatement(sql)) {

        stmt.setString(1, iban);

        try (ResultSet rs = stmt.executeQuery()) {
            if (rs.next()) {
                return rs.getString("balance");
            }
        }
    }

    return "0.0";
}
