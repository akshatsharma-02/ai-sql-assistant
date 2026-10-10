# Evaluation results

**Model:** openai/gpt-oss-120b  
**Execution accuracy:** 22/22 (100%)

- easy: 5/5
- medium: 7/7
- hard: 8/8
- unanswerable: 2/2

| # | Level | Result | Retried | Question | SQL or error |
|---|---|---|---|---|---|
| 1 | easy | PASS |  | How many customers are there? | `SELECT COUNT(*) AS CustomerCount FROM Customer` |
| 2 | easy | PASS |  | List all product categories. | `SELECT ProductCategory FROM ProductCategory LIMIT 100` |
| 3 | easy | PASS |  | What is the most expensive product and its unit price? | `SELECT ProductName, ROUND(ProductUnitPrice, 2) AS UnitPrice FROM Product ORDER BY ProductUnitPrice DESC LIMIT 1` |
| 4 | easy | PASS |  | How many products cost more than 50? | `SELECT COUNT(*) FROM Product WHERE ProductUnitPrice > 50` |
| 5 | easy | PASS |  | What is the average product unit price? | `SELECT ROUND(AVG(ProductUnitPrice), 2) AS AvgUnitPrice FROM Product` |
| 6 | medium | PASS |  | How many customers are in each country? Show the country and the count. | `SELECT Country.Country AS Country, COUNT(Customer.CustomerID) AS CustomerCount FROM Country JOIN Customer ON Customer.CountryID = Country.CountryID GROUP BY Country.Country LIMIT 100` |
| 7 | medium | PASS |  | How many products are in each product category? | `SELECT pc.ProductCategory, COUNT(p.ProductID) AS ProductCount FROM Product p JOIN ProductCategory pc ON p.ProductCategoryID = pc.ProductCategoryID GROUP BY pc.ProductCategory LIMIT 100` |
| 8 | medium | PASS |  | What is the total revenue across all orders? | `SELECT ROUND(SUM(od.QuantityOrdered * p.ProductUnitPrice), 2) AS TotalRevenue FROM OrderDetail od JOIN Product p ON od.ProductID = p.ProductID` |
| 9 | medium | PASS |  | What are the top 5 products by total quantity ordered? | `SELECT p.ProductName, SUM(od.QuantityOrdered) AS TotalQuantity FROM OrderDetail od JOIN Product p ON od.ProductID = p.ProductID GROUP BY p.ProductID, p.ProductName ORDER BY TotalQuantity DESC LIMIT 5` |
| 10 | medium | PASS |  | Which countries are in the Western Europe region? | `SELECT Country FROM Country JOIN Region USING (RegionID) WHERE Region = 'Western Europe' LIMIT 100` |
| 11 | medium | PASS |  | What was the total revenue in 2015? | `SELECT ROUND(SUM(od.QuantityOrdered * p.ProductUnitPrice), 2) AS TotalRevenue2015 FROM OrderDetail od JOIN Product p ON od.ProductID = p.ProductID WHERE strftime('%Y', od.OrderDate) = '2015'` |
| 12 | medium | PASS |  | How many orders were placed in each year? | `SELECT strftime('%Y', OrderDate) AS Year, COUNT(DISTINCT OrderID) AS OrderCount FROM OrderDetail GROUP BY Year ORDER BY Year LIMIT 100` |
| 13 | hard | PASS |  | What is the total revenue for each region, from highest to lowest? | `SELECT r.Region AS Region, ROUND(SUM(od.QuantityOrdered * p.ProductUnitPrice), 2) AS TotalRevenue FROM OrderDetail od JOIN Customer c ON od.CustomerID = c.CustomerID JOIN Country co ON c.CountryID = co.CountryID JOIN Region r ON co.RegionID = r.RegionID JOIN Product p ON od.ProductID = p.ProductID GROUP BY r.Region ORDER BY TotalRevenue DESC LIMIT 100` |
| 14 | hard | PASS |  | Who are the top 3 customers by total revenue? Show their full names and revenue. | `SELECT Customer.FirstName // ' ' // Customer.LastName AS FullName,        ROUND(SUM(OrderDetail.QuantityOrdered * Product.ProductUnitPrice), 2) AS Revenue FROM OrderDetail JOIN Customer ON OrderDetail.CustomerID = Customer.CustomerID JOIN Product ON OrderDetail.ProductID = Product.ProductID GROUP BY Customer.CustomerID ORDER BY Revenue DESC LIMIT 3` |
| 15 | hard | PASS |  | Which product category had the highest revenue in 2014? | `SELECT pc.ProductCategory FROM OrderDetail od JOIN Product p ON od.ProductID = p.ProductID JOIN ProductCategory pc ON p.ProductCategoryID = pc.ProductCategoryID WHERE strftime('%Y', od.OrderDate) = '2014' GROUP BY pc.ProductCategory ORDER BY SUM(od.QuantityOrdered * p.ProductUnitPrice) DESC LIMIT 1` |
| 16 | hard | PASS |  | Which month had the highest total revenue? Show the month as YYYY-MM. | `SELECT strftime('%Y-%m', od.OrderDate) AS Month,        ROUND(SUM(od.QuantityOrdered * p.ProductUnitPrice), 2) AS TotalRevenue FROM OrderDetail od JOIN Product p ON od.ProductID = p.ProductID GROUP BY Month ORDER BY TotalRevenue DESC LIMIT 1` |
| 17 | hard | PASS |  | How many distinct customers bought Seafood products? | `SELECT COUNT(DISTINCT Customer.CustomerID) AS DistinctCustomerCount FROM OrderDetail JOIN Customer ON OrderDetail.CustomerID = Customer.CustomerID JOIN Product ON OrderDetail.ProductID = Product.ProductID JOIN ProductCategory ON Product.ProductCategoryID = ProductCategory.ProductCategoryID WHERE ProductCategory.ProductCategory = 'Seafood'` |
| 18 | hard | PASS |  | What is the average revenue per order line for customers in Germany? | `SELECT ROUND(AVG(od.QuantityOrdered * p.ProductUnitPrice), 2) AS AvgRevenuePerOrderLine FROM OrderDetail od JOIN Customer c ON od.CustomerID = c.CustomerID JOIN Country co ON c.CountryID = co.CountryID JOIN Product p ON od.ProductID = p.ProductID WHERE co.Country = 'Germany'` |
| 19 | hard | PASS |  | Which products have a unit price above the average product price? | `SELECT ProductName, ROUND(ProductUnitPrice, 2) AS UnitPrice FROM Product WHERE ProductUnitPrice > (SELECT AVG(ProductUnitPrice) FROM Product) LIMIT 100` |
| 20 | hard | PASS |  | What was total revenue by year? Show the year and revenue in chronological order. | `SELECT strftime('%Y', OrderDate) AS Year, ROUND(SUM(QuantityOrdered * ProductUnitPrice), 2) AS Revenue FROM OrderDetail JOIN Product USING (ProductID) GROUP BY Year ORDER BY Year ASC LIMIT 100` |
| 21 | unanswerable | PASS |  | What is the shipping cost for each order? | `This question can't be answered from the sales database.` |
| 22 | unanswerable | PASS |  | Which employee handled the most orders? | `This question can't be answered from the sales database.` |
