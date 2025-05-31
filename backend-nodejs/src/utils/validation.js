
// backend/src/utils/validation.js
'use strict';

export const validateEmail = (email) => {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return re.test(email);
};

export const validatePassword = (password) => {
  // At least 8 characters, 1 uppercase, 1 lowercase, 1 number
  const re = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[a-zA-Z\d]{8,}$/;
  return re.test(password);
};

export const sanitizeInput = (input) => {
  // Remove HTML tags and special characters
  return input.replace(/<[^>]*>?/gm, '')
             .replace(/[<>'"]/g, '');
};