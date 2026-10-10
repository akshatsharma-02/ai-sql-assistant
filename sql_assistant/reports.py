"""
Built-in reports: hand-written SQL for common business questions.

These run without the LLM, so the app stays useful even with no API key.
Values chosen by the user (like a customer name) are passed as query
parameters (the ? placeholders), never pasted into the SQL text. That is
the standard defence against SQL injection: the database treats the value
as data, so a name like  x'; DROP TABLE Customer; --  is just an odd name.
"""

REVENUE = "od.QuantityOrdered * p.ProductUnitPrice"

REPORTS = {
    "Revenue by region": {
        "description": "Total revenue for each region, highest first.",
        "sql": f"""
            SELECT r.Region, ROUND(SUM({REVENUE}), 2) AS Revenue
            FROM OrderDetail od
            JOIN Product p   ON p.ProductID = od.ProductID
            JOIN Customer c  ON c.CustomerID = od.CustomerID
            JOIN Country co  ON co.CountryID = c.CountryID
            JOIN Region r    ON r.RegionID = co.RegionID
            GROUP BY r.Region
            ORDER BY Revenue DESC""",
        "needs_customer": False,
    },
    "Top 10 products by revenue": {
        "description": "The ten products that brought in the most revenue.",
        "sql": f"""
            SELECT p.ProductName, ROUND(SUM({REVENUE}), 2) AS Revenue
            FROM OrderDetail od
            JOIN Product p ON p.ProductID = od.ProductID
            GROUP BY p.ProductName
            ORDER BY Revenue DESC
            LIMIT 10""",
        "needs_customer": False,
    },
    "Monthly revenue trend": {
        "description": "Revenue for every month in the data.",
        "sql": f"""
            SELECT strftime('%Y-%m', od.OrderDate) AS Month, ROUND(SUM({REVENUE}), 2) AS Revenue
            FROM OrderDetail od
            JOIN Product p ON p.ProductID = od.ProductID
            GROUP BY Month
            ORDER BY Month""",
        "needs_customer": False,
    },
    "Revenue by product category": {
        "description": "Revenue and units sold for each category.",
        "sql": f"""
            SELECT pc.ProductCategory,
                   SUM(od.QuantityOrdered) AS UnitsSold,
                   ROUND(SUM({REVENUE}), 2) AS Revenue
            FROM OrderDetail od
            JOIN Product p          ON p.ProductID = od.ProductID
            JOIN ProductCategory pc ON pc.ProductCategoryID = p.ProductCategoryID
            GROUP BY pc.ProductCategory
            ORDER BY Revenue DESC""",
        "needs_customer": False,
    },
    "Customer summary": {
        "description": "Orders, units, and revenue for one customer.",
        "sql": f"""
            SELECT c.FirstName || ' ' || c.LastName AS Customer,
                   COUNT(*) AS Orders,
                   SUM(od.QuantityOrdered) AS Units,
                   ROUND(SUM({REVENUE}), 2) AS Revenue,
                   MIN(od.OrderDate) AS FirstOrder,
                   MAX(od.OrderDate) AS LastOrder
            FROM OrderDetail od
            JOIN Customer c ON c.CustomerID = od.CustomerID
            JOIN Product p  ON p.ProductID = od.ProductID
            WHERE c.FirstName || ' ' || c.LastName = ?
            GROUP BY c.CustomerID""",
        "needs_customer": True,
    },
}

CUSTOMER_NAMES_SQL = """
    SELECT FirstName || ' ' || LastName AS Name
    FROM Customer
    ORDER BY Name"""
