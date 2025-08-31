import type { AnalysisError } from "../../types";

export class AppError extends Error {
  public readonly statusCode: number;
  public readonly errorType: AnalysisError;
  public readonly isOperational: boolean;

  constructor(
    message: string,
    statusCode: number = 500,
    errorType: AnalysisError = "api-error",
    isOperational: boolean = true
  ) {
    super(message);
    this.statusCode = statusCode;
    this.errorType = errorType;
    this.isOperational = isOperational;

    Error.captureStackTrace(this, this.constructor);
  }
}

export class ValidationError extends AppError {
  constructor(message: string, errorType: AnalysisError = "api-error") {
    super(message, 400, errorType);
  }
}

export class DataNotFoundError extends AppError {
  constructor(message: string = "Data not found") {
    super(message, 404, "api-error");
  }
}

export class InsufficientDataError extends AppError {
  constructor(message: string = "Insufficient data for analysis") {
    super(message, 400, "insufficient-data");
  }
}

export class NoOrdersError extends AppError {
  constructor(message: string = "No orders found in store") {
    super(message, 400, "no-orders");
  }
}

export class NoProductsError extends AppError {
  constructor(message: string = "No products found in store") {
    super(message, 400, "no-products");
  }
}
